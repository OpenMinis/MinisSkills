"""
Telegram client — 基于 Telethon 的本地优先消息同步与查询客户端。

改造来源：jackwener/tg-cli
https://github.com/jackwener/tg-cli/blob/main/src/tg_cli/client.py

主要改动：
- 移除 click / rich / python-dotenv / pyyaml 依赖
- 移除 CLI 层，所有功能封装为同步 Python API
- 认证通过手机号交互登录（首次）+ session 文件持久化（后续免登录）
- 默认 session/db 路径改为 /var/minis/workspace/tg-hub/
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import defaultdict
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel, Chat, User

from .config import (
    get_api_hash,
    get_api_id,
    get_app_version,
    get_device_model,
    get_lang_code,
    get_session_path,
    get_system_lang_code,
    get_system_version,
    is_default_api_id,
)
from .db import MessageDB

log = logging.getLogger(__name__)

_FIRST_SYNC_LIMIT = 500


# ─── 内部工具 ─────────────────────────────────────────────────────────────────

def _get_sender_name(sender: User | Channel | Chat | None) -> str | None:
    if sender is None:
        return None
    if isinstance(sender, User):
        parts = [sender.first_name or "", sender.last_name or ""]
        name = " ".join(p for p in parts if p)
        return name or sender.username or str(sender.id)
    return getattr(sender, "title", None) or str(sender.id)


def _run(coro):
    return asyncio.run(coro)


_default_api_warned = False


@asynccontextmanager
async def _connect() -> AsyncGenerator[TelegramClient, None]:
    """异步上下文管理器：连接 Telegram，退出时自动断开。"""
    global _default_api_warned

    api_id = get_api_id()
    api_hash = get_api_hash()

    if not _default_api_warned and is_default_api_id():
        _default_api_warned = True
        log.warning(
            "Using default Telegram Desktop API credentials (api_id=2040). "
            "This increases the risk of account restrictions. "
            "Get your own at https://my.telegram.org and set TG_API_ID / TG_API_HASH."
        )

    c = TelegramClient(
        get_session_path(),
        api_id,
        api_hash,
        device_model=get_device_model(),
        system_version=get_system_version(),
        app_version=get_app_version(),
        lang_code=get_lang_code(),
        system_lang_code=get_system_lang_code(),
        flood_sleep_threshold=120,
    )
    await c.start()
    try:
        yield c
    finally:
        await c.disconnect()


# ─── 底层异步函数 ─────────────────────────────────────────────────────────────

async def _list_chats(client: TelegramClient, chat_type: str | None = None) -> list[dict]:
    results = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        t = "unknown"
        if isinstance(entity, User):
            t = "user"
        elif isinstance(entity, Chat):
            t = "group"
        elif isinstance(entity, Channel):
            t = "channel" if entity.broadcast else "supergroup"
        if chat_type and t != chat_type:
            continue
        results.append({
            "id": dialog.id,
            "name": dialog.name,
            "type": t,
            "unread": dialog.unread_count,
        })
    return results


async def _get_me(client: TelegramClient) -> dict:
    me = await client.get_me()
    return {
        "id": me.id,
        "name": _get_sender_name(me) or "",
        "username": me.username or "",
        "phone": me.phone or "",
    }


async def _fetch_history(
    client: TelegramClient,
    chat: str | int,
    limit: int = 1000,
    db: MessageDB | None = None,
    on_progress: Callable[[int], None] | None = None,
    min_id: int = 0,
    batch_delay: float = 0.5,
) -> int:
    """拉取历史消息存入 SQLite，返回新增条数。"""
    owns_db = db is None
    if db is None:
        db = MessageDB()
    inserted = 0
    try:
        entity = await client.get_entity(chat)
        chat_name = (
            getattr(entity, "title", None)
            or getattr(entity, "first_name", None)
            or str(chat)
        )
        chat_id = entity.id

        sender_cache: dict[int, str] = {}
        batch: list[dict] = []
        BATCH = 200

        async for msg in client.iter_messages(entity, limit=limit, min_id=min_id):
            if msg.text is None and msg.message is None:
                continue

            sender_name = None
            if msg.sender_id:
                if msg.sender_id in sender_cache:
                    sender_name = sender_cache[msg.sender_id]
                else:
                    try:
                        sender = await msg.get_sender()
                        sender_name = _get_sender_name(sender)
                    except Exception:
                        sender_name = None
                    if sender_name:
                        sender_cache[msg.sender_id] = sender_name

            content = msg.text or msg.message or ""
            ts = msg.date
            if ts and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            batch.append(dict(
                chat_id=chat_id, chat_name=chat_name, msg_id=msg.id,
                sender_id=msg.sender_id, sender_name=sender_name,
                content=content, timestamp=ts or datetime.now(timezone.utc),
            ))
            if len(batch) >= BATCH:
                inserted += db.insert_batch(batch)
                batch.clear()
                if on_progress:
                    on_progress(inserted)
                if batch_delay > 0:
                    jitter = batch_delay * random.uniform(-0.3, 0.3)
                    await asyncio.sleep(batch_delay + jitter)

        if batch:
            inserted += db.insert_batch(batch)
        return inserted
    except FloodWaitError as e:
        log.warning("Telegram rate limit hit, waiting %ss...", e.seconds)
        await asyncio.sleep(e.seconds + random.uniform(1, 3))
        return inserted
    finally:
        if owns_db:
            db.close()


async def _sync_all(
    client: TelegramClient,
    db: MessageDB,
    limit_per_chat: int = 5000,
    on_chat_done: Callable[[str, int], None] | None = None,
    delay: float = 1.0,
    max_chats: int | None = None,
) -> dict[str, int]:
    results: dict[str, int] = {}
    stored = {c["chat_id"]: c for c in db.get_chats()}
    dialog_cache: dict[int, tuple[Any, str]] = {}
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        dialog_cache[entity.id] = (entity, dialog.name)

    items = list(dialog_cache.items())
    if max_chats is not None:
        items = items[:max_chats]
    total = len(items)

    for idx, (chat_id, (entity, dialog_name)) in enumerate(items):
        chat_info = stored.get(chat_id, {})
        chat_name = chat_info.get("chat_name") or dialog_name or str(chat_id)
        last_id = db.get_last_msg_id(chat_id) or 0
        effective_limit = limit_per_chat
        if last_id == 0 and limit_per_chat > _FIRST_SYNC_LIMIT:
            effective_limit = _FIRST_SYNC_LIMIT
        try:
            count = await _fetch_history(
                client,
                entity,
                limit=effective_limit,
                db=db,
                min_id=last_id,
            )
            results[chat_name] = count
            if on_chat_done:
                on_chat_done(chat_name, count)
        except FloodWaitError as e:
            log.warning("%s rate limited, waiting %ss...", chat_name, e.seconds)
            await asyncio.sleep(e.seconds + random.uniform(1, 3))
            results[chat_name] = 0
        except Exception as e:
            log.warning("同步 %s 失败: %s", chat_name, e)
            results[chat_name] = 0

        if delay > 0 and idx < total - 1:
            jitter = delay * random.uniform(-0.2, 0.2)
            await asyncio.sleep(delay + jitter)
    return results


# ─── 同步公开 API ─────────────────────────────────────────────────────────────

class TGClient:
    """
    tg-hub 核心客户端，提供同步接口。

    首次使用需要交互式登录（手机号 + 验证码），之后 session 自动复用。
    建议优先使用你自己的 Telegram APP ID / APP HASH，降低公共凭证被滥用带来的风控风险。

    用法：
        client = TGClient()
        client.login()        # 首次登录（需要 terminal）
        chats = client.list_chats()
        client.sync("群名")
        msgs = client.search("关键词", hours=24)
    """

    # ── 认证 ──────────────────────────────────────────────────────────────

    def login(self) -> dict:
        """
        交互式登录（首次使用）。
        需要在 terminal 中输入手机号和验证码。
        登录成功后 session 保存到 /var/minis/workspace/tg-hub/，后续免登录。
        """
        async def _do():
            async with _connect() as c:
                return await _get_me(c)
        return _run(_do())

    def whoami(self) -> dict:
        """获取当前登录账号信息。"""
        async def _do():
            async with _connect() as c:
                return await _get_me(c)
        return _run(_do())

    # ── 聊天列表 ──────────────────────────────────────────────────────────

    def list_chats(self, chat_type: str | None = None) -> list[dict]:
        """
        列出所有对话（从 Telegram 实时获取）。

        Args:
            chat_type: 过滤类型，可选 "user" / "group" / "channel" / "supergroup"

        Returns:
            [{"id": ..., "name": ..., "type": ..., "unread": ...}, ...]
        """
        async def _do():
            async with _connect() as c:
                return await _list_chats(c, chat_type)
        return _run(_do())

    # ── 同步 ──────────────────────────────────────────────────────────────

    def sync(self, chat: str | int, limit: int = 5000) -> int:
        """
        同步单个聊天的消息到本地 SQLite（增量）。

        Args:
            chat:  群名、用户名或数字 ID
            limit: 最多同步多少条

        Returns:
            新增消息条数
        """
        def _progress(n: int):
            log.info("已同步 %d 条...", n)

        async def _do():
            async with _connect() as c:
                with MessageDB() as db:
                    return await _fetch_history(c, chat, limit=limit, db=db, on_progress=_progress)
        return _run(_do())

    def sync_all(
        self,
        limit_per_chat: int = 5000,
        *,
        delay: float = 1.0,
        max_chats: int | None = None,
    ) -> dict[str, int]:
        """
        同步所有对话到本地 SQLite（增量）。

        Args:
            limit_per_chat: 每个 chat 最多同步多少条
            delay: chat 之间的等待秒数（带随机抖动）
            max_chats: 本轮最多同步多少个 chat

        Returns:
            {chat_name: new_count, ...}
        """
        def _on_done(name: str, count: int):
            if count > 0:
                log.info("✓ %s: +%d 条", name, count)

        async def _do():
            async with _connect() as c:
                with MessageDB() as db:
                    return await _sync_all(
                        c,
                        db,
                        limit_per_chat=limit_per_chat,
                        on_chat_done=_on_done,
                        delay=delay,
                        max_chats=max_chats,
                    )
        return _run(_do())

    def refresh(
        self,
        limit_per_chat: int = 500,
        *,
        delay: float = 1.0,
        max_chats: int | None = None,
    ) -> dict[str, int]:
        """快速增量刷新所有对话（每个群最多 500 条新消息）。"""
        return self.sync_all(limit_per_chat=limit_per_chat, delay=delay, max_chats=max_chats)

    # ── 本地查询（不联网）──────────────────────────────────────────────────

    def search(
        self,
        keyword: str,
        *,
        chat: str | None = None,
        sender: str | None = None,
        hours: int | None = None,
        regex: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """
        在本地 SQLite 中搜索消息。

        Args:
            keyword: 关键词（或正则表达式，需 regex=True）
            chat:    按群名过滤
            sender:  按发送者过滤
            hours:   只搜索最近 N 小时
            regex:   是否使用正则模式
            limit:   最多返回条数

        Returns:
            [{"chat_name", "sender_name", "content", "timestamp", ...}, ...]
        """
        with MessageDB() as db:
            chat_id = db.resolve_chat_id(chat) if chat else None
            if regex:
                return db.search_regex(keyword, chat_id=chat_id, sender=sender, hours=hours, limit=limit)
            return db.search(keyword, chat_id=chat_id, sender=sender, hours=hours, limit=limit)

    def filter(
        self,
        keywords: str | list[str],
        *,
        chat: str | None = None,
        hours: int | None = None,
    ) -> list[dict]:
        """
        多关键词 OR 过滤（逗号分隔字符串或列表）。

        示例：
            client.filter("Rust,Golang,remote", hours=48)
            client.filter(["招聘", "remote"], chat="某群")
        """
        if isinstance(keywords, str):
            kws = [k.strip() for k in keywords.split(",") if k.strip()]
        else:
            kws = [k.strip() for k in keywords if k.strip()]
        if not kws:
            return []

        pattern = re.compile("|".join(re.escape(k) for k in kws), re.IGNORECASE)
        with MessageDB() as db:
            chat_id = db.resolve_chat_id(chat) if chat else None
            if hours:
                msgs = db.get_recent(chat_id=chat_id, hours=hours, limit=100000)
            else:
                msgs = db.get_today(chat_id=chat_id)
        return [m for m in msgs if m.get("content") and pattern.search(m["content"])]

    def today(self, chat: str | None = None) -> list[dict]:
        """获取今天的消息（按本地时区）。"""
        with MessageDB() as db:
            chat_id = db.resolve_chat_id(chat) if chat else None
            return db.get_today(chat_id=chat_id)

    def recent(
        self,
        hours: int = 24,
        *,
        chat: str | None = None,
        sender: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """获取最近 N 小时的消息（按时间正序）。"""
        with MessageDB() as db:
            chat_id = db.resolve_chat_id(chat) if chat else None
            return db.get_recent(chat_id=chat_id, sender=sender, hours=hours, limit=limit)

    def top_senders(
        self,
        chat: str | None = None,
        hours: int | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """获取发言最多的用户排行。"""
        with MessageDB() as db:
            chat_id = db.resolve_chat_id(chat) if chat else None
            return db.top_senders(chat_id=chat_id, hours=hours, limit=limit)

    def timeline(
        self,
        chat: str | None = None,
        hours: int | None = None,
        granularity: str = "day",
    ) -> list[dict]:
        """获取消息数量按时间分布（day 或 hour 粒度）。"""
        with MessageDB() as db:
            chat_id = db.resolve_chat_id(chat) if chat else None
            return db.timeline(chat_id=chat_id, hours=hours, granularity=granularity)

    def stats(self) -> dict:
        """获取本地数据库统计（各群消息数）。"""
        with MessageDB() as db:
            chats = db.get_chats()
            total = db.count()
        return {"total": total, "chats": chats}

    def local_chats(self) -> list[dict]:
        """列出本地数据库中已同步的群（不联网）。"""
        with MessageDB() as db:
            return db.get_chats()

    def delete_chat(self, chat: str) -> int:
        """从本地数据库删除某个群的所有消息，返回删除条数。"""
        with MessageDB() as db:
            chat_id = db.resolve_chat_id(chat)
            if not chat_id:
                raise ValueError(f"找不到群：{chat}")
            return db.delete_chat(chat_id)
