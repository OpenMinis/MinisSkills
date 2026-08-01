"""
SQLite message store for tg-hub.

改造来源：jackwener/tg-cli
https://github.com/jackwener/tg-cli/blob/main/src/tg_cli/db.py
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import get_db_path

log = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    platform      TEXT    NOT NULL DEFAULT 'telegram',
    chat_id       INTEGER NOT NULL,
    chat_name     TEXT,
    msg_id        INTEGER NOT NULL,
    sender_id     INTEGER,
    sender_name   TEXT,
    content       TEXT,
    timestamp     TEXT    NOT NULL,
    raw_json      TEXT,
    UNIQUE(platform, chat_id, msg_id)
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_content ON messages(content);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_name);
"""


def _canonical_chat_id(chat_id: int) -> int:
    """Normalize Telegram chat IDs to the bare numeric ID stored in SQLite.

    Only strips the -100 prefix from negative IDs (Telegram's convention for
    channels/supergroups).  Positive IDs starting with 100 are left as-is.
    """
    if chat_id < 0:
        digits = str(abs(chat_id))
        if digits.startswith("100") and len(digits) > 3:
            return int(digits[3:])
        return abs(chat_id)
    return chat_id


class MessageDB:
    """SQLite message store with context manager support."""

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            self.db_path = get_db_path()
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_CREATE_TABLE + _CREATE_INDEX)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def find_chats(self, chat_str: str) -> list[dict]:
        """Return chats matching a numeric ID, exact name, or partial name."""
        chats = self.get_chats()

        try:
            numeric_id = _canonical_chat_id(int(chat_str))
            exact_id_matches = [c for c in chats if c["chat_id"] == numeric_id]
            if exact_id_matches:
                return exact_id_matches
        except ValueError:
            pass

        exact_name_matches = [
            c
            for c in chats
            if c["chat_name"] and c["chat_name"].casefold() == chat_str.casefold()
        ]
        if exact_name_matches:
            return exact_name_matches

        partial_matches = [
            c
            for c in chats
            if c["chat_name"] and chat_str.casefold() in c["chat_name"].casefold()
        ]
        return partial_matches

    def resolve_chat_id(self, chat_str: str) -> int | None:
        """Resolve a chat string (name or numeric ID) to a unique database chat_id."""
        matches = self.find_chats(chat_str)
        if len(matches) == 1:
            return matches[0]["chat_id"]
        return None

    def insert_message(
        self,
        *,
        platform: str = "telegram",
        chat_id: int,
        chat_name: str | None,
        msg_id: int,
        sender_id: int | None,
        sender_name: str | None,
        content: str | None,
        timestamp: datetime,
        raw_json: dict[str, Any] | None = None,
    ) -> bool:
        """Insert a message, returns True if inserted (not duplicate)."""
        try:
            cursor = self.conn.execute(
                """INSERT OR IGNORE INTO messages
                   (
                       platform,
                       chat_id,
                       chat_name,
                       msg_id,
                       sender_id,
                       sender_name,
                       content,
                       timestamp,
                       raw_json
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    platform,
                    chat_id,
                    chat_name,
                    msg_id,
                    sender_id,
                    sender_name,
                    content,
                    timestamp.isoformat(),
                    json.dumps(raw_json, ensure_ascii=False) if raw_json else None,
                ),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            log.debug("insert_message failed: %s", e)
            return False

    def insert_batch(self, messages: list[dict], platform: str = "telegram") -> int:
        """Batch insert messages in a single transaction.

        Returns the number of rows actually inserted, excluding duplicates.
        """
        if not messages:
            return 0
        rows = [
            (
                platform,
                m["chat_id"],
                m.get("chat_name"),
                m["msg_id"],
                m.get("sender_id"),
                m.get("sender_name"),
                m.get("content"),
                (
                    m["timestamp"].isoformat()
                    if isinstance(m["timestamp"], datetime)
                    else m["timestamp"]
                ),
                json.dumps(m["raw_json"], ensure_ascii=False) if m.get("raw_json") else None,
            )
            for m in messages
        ]
        try:
            before = self.conn.total_changes
            self.conn.executemany(
                """INSERT OR IGNORE INTO messages
                   (
                       platform,
                       chat_id,
                       chat_name,
                       msg_id,
                       sender_id,
                       sender_name,
                       content,
                       timestamp,
                       raw_json
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            self.conn.commit()
            return self.conn.total_changes - before
        except sqlite3.Error as e:
            log.warning("insert_batch failed: %s", e)
            return 0

    def search(
        self,
        keyword: str,
        chat_id: int | None = None,
        sender: str | None = None,
        hours: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search messages by keyword."""
        query = "SELECT * FROM messages WHERE content LIKE ?"
        params: list[Any] = [f"%{keyword}%"]
        if chat_id:
            query += " AND chat_id = ?"
            params.append(chat_id)
        if sender:
            query += " AND sender_name LIKE ?"
            params.append(f"%{sender}%")
        if hours:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def search_regex(
        self,
        pattern: str,
        chat_id: int | None = None,
        sender: str | None = None,
        hours: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search messages by regex pattern."""
        regex = re.compile(pattern, re.IGNORECASE)
        query = "SELECT * FROM messages WHERE content IS NOT NULL"
        params: list[Any] = []
        if chat_id:
            query += " AND chat_id = ?"
            params.append(chat_id)
        if sender:
            query += " AND sender_name LIKE ?"
            params.append(f"%{sender}%")
        if hours:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)
        query += " ORDER BY timestamp DESC"

        rows = self.conn.execute(query, params).fetchall()
        results: list[dict] = []
        for row in rows:
            msg = dict(row)
            content = msg.get("content") or ""
            if regex.search(content):
                results.append(msg)
                if len(results) >= limit:
                    break
        return results

    def get_recent(
        self,
        chat_id: int | None = None,
        sender: str | None = None,
        hours: int | None = 24,
        limit: int = 500,
    ) -> list[dict]:
        """Get the latest messages, returned in chronological order."""
        if hours is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            base_query = "SELECT * FROM messages WHERE timestamp >= ?"
            params: list[Any] = [cutoff]
        else:
            base_query = "SELECT * FROM messages WHERE 1=1"
            params = []
        if chat_id:
            base_query += " AND chat_id = ?"
            params.append(chat_id)
        if sender:
            base_query += " AND sender_name LIKE ?"
            params.append(f"%{sender}%")
        query = (
            f"SELECT * FROM ({base_query} ORDER BY timestamp DESC LIMIT ?) "
            "ORDER BY timestamp ASC"
        )
        rows = self.conn.execute(query, params + [limit]).fetchall()
        return [dict(r) for r in rows]

    def get_today(
        self,
        chat_id: int | None = None,
        tz_offset_hours: int | None = None,
        limit: int = 5000,
    ) -> list[dict]:
        """Get today's messages (in local timezone).

        Args:
            tz_offset_hours: Local timezone offset from UTC.
                             If None, auto-detect from system timezone.
        """
        # Today 00:00 in local time → UTC
        now_utc = datetime.now(timezone.utc)
        if tz_offset_hours is not None:
            local_tz = timezone(timedelta(hours=tz_offset_hours))
        else:
            # Auto-detect system timezone
            local_tz = datetime.now().astimezone().tzinfo
        today_local = now_utc.astimezone(local_tz).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        cutoff_utc = today_local.astimezone(timezone.utc).isoformat()

        query = "SELECT * FROM messages WHERE timestamp >= ?"
        params: list[Any] = [cutoff_utc]
        if chat_id:
            query += " AND chat_id = ?"
            params.append(chat_id)
        query += " ORDER BY chat_name, timestamp ASC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_chats(self) -> list[dict]:
        """Get all known chats with message counts."""
        rows = self.conn.execute(
            """SELECT chat_id, chat_name, COUNT(*) as msg_count,
                      MIN(timestamp) as first_msg, MAX(timestamp) as last_msg
               FROM messages
               GROUP BY chat_id
               ORDER BY msg_count DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def get_last_msg_id(self, chat_id: int) -> int | None:
        """Get the latest msg_id for a chat, used for incremental sync."""
        row = self.conn.execute(
            "SELECT MAX(msg_id) FROM messages WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return row[0] if row and row[0] is not None else None

    def count(self, chat_id: int | None = None) -> int:
        if chat_id:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM messages WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        return row[0]

    def get_latest_timestamp(self, chat_id: int | None = None) -> str | None:
        """Return the latest stored message timestamp for a chat or the whole DB."""
        if chat_id:
            row = self.conn.execute(
                "SELECT MAX(timestamp) FROM messages WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT MAX(timestamp) FROM messages").fetchone()
        return row[0] if row and row[0] is not None else None

    def delete_chat(self, chat_id: int) -> int:
        """Delete all messages for a chat. Returns number of deleted rows."""
        cursor = self.conn.execute(
            "DELETE FROM messages WHERE chat_id = ?", (chat_id,)
        )
        self.conn.commit()
        return cursor.rowcount

    def top_senders(
        self,
        chat_id: int | None = None,
        hours: int | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get most active senders ranked by message count."""
        conditions = ["(sender_id IS NOT NULL OR sender_name IS NOT NULL)"]
        params: list[Any] = []
        if chat_id:
            conditions.append("chat_id = ?")
            params.append(chat_id)
        if hours:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            conditions.append("timestamp >= ?")
            params.append(cutoff)

        where = " AND ".join(conditions)
        rows = self.conn.execute(
            f"""SELECT MAX(sender_name) as sender_name, sender_id, COUNT(*) as msg_count,
                       MIN(timestamp) as first_msg, MAX(timestamp) as last_msg
                FROM messages WHERE {where}
                GROUP BY COALESCE(CAST(sender_id AS TEXT), 'name:' || COALESCE(sender_name, ''))
                ORDER BY msg_count DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def timeline(
        self,
        chat_id: int | None = None,
        hours: int | None = None,
        granularity: str = "day",
    ) -> list[dict]:
        """Get message count grouped by time period."""
        if granularity == "hour":
            time_expr = "substr(timestamp, 1, 13)"  # YYYY-MM-DDTHH
        else:
            time_expr = "substr(timestamp, 1, 10)"  # YYYY-MM-DD

        conditions = ["1=1"]
        params: list[Any] = []
        if chat_id:
            conditions.append("chat_id = ?")
            params.append(chat_id)
        if hours:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            conditions.append("timestamp >= ?")
            params.append(cutoff)

        where = " AND ".join(conditions)
        rows = self.conn.execute(
            f"""SELECT {time_expr} as period, COUNT(*) as msg_count
                FROM messages WHERE {where}
                GROUP BY period
                ORDER BY period ASC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
