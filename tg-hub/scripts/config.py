"""
Configuration — 直接从环境变量读取，移除 python-dotenv 依赖。

改造来源：jackwener/tg-cli
https://github.com/jackwener/tg-cli/blob/main/src/tg_cli/config.py

主要改动：
- 移除 python-dotenv，改为直接读取环境变量
- 默认 session/db 路径改为 /var/minis/workspace/tg-hub/
"""

from __future__ import annotations

import os
from pathlib import Path

# Telegram Desktop 内置公共凭证（无需自己申请）
_DEFAULT_API_ID   = 2040
_DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

# 默认数据目录：存放在 home 目录下，跨 session 复用
_DEFAULT_DATA_DIR = Path.home() / ".tg-hub"


def get_api_id() -> int:
    val = os.environ.get("TG_API_ID", "")
    return int(val) if val else _DEFAULT_API_ID


def get_api_hash() -> str:
    return os.environ.get("TG_API_HASH", _DEFAULT_API_HASH)


def get_data_dir() -> Path:
    raw = os.environ.get("TG_DATA_DIR", "")
    d = Path(raw).expanduser() if raw else _DEFAULT_DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_session_path() -> str:
    name = os.environ.get("TG_SESSION_NAME", "tg_hub")
    return str(get_data_dir() / name)


def get_db_path() -> Path:
    raw = os.environ.get("TG_DB_PATH", "")
    if raw:
        p = Path(raw).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return get_data_dir() / "messages.db"
