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

# Telegram Desktop 内置公共凭证（仅作兜底，不推荐长期使用）
_DEFAULT_API_ID   = 2040
_DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

# 上游 tg-cli 采用的 Telegram Desktop 5.x 指纹
_DEFAULT_DEVICE_MODEL = "Desktop"
_DEFAULT_SYSTEM_VERSION = "macOS 15.3"
_DEFAULT_APP_VERSION = "5.12.1"
_DEFAULT_LANG_CODE = "en"
_DEFAULT_SYSTEM_LANG_CODE = "en-US"

# 默认数据目录：存放在 home 目录下，跨 session 复用
_DEFAULT_DATA_DIR = Path.home() / ".tg-hub"


def is_default_api_id() -> bool:
    """Return True if the user has NOT set a custom TG_API_ID."""
    return not os.environ.get("TG_API_ID", "")


def get_api_id() -> int:
    val = os.environ.get("TG_API_ID", "")
    return int(val) if val else _DEFAULT_API_ID


def get_api_hash() -> str:
    val = os.environ.get("TG_API_HASH", "")
    return val if val else _DEFAULT_API_HASH


def get_device_model() -> str:
    return os.environ.get("TG_DEVICE_MODEL", _DEFAULT_DEVICE_MODEL)


def get_system_version() -> str:
    return os.environ.get("TG_SYSTEM_VERSION", _DEFAULT_SYSTEM_VERSION)


def get_app_version() -> str:
    return os.environ.get("TG_APP_VERSION", _DEFAULT_APP_VERSION)


def get_lang_code() -> str:
    return os.environ.get("TG_LANG_CODE", _DEFAULT_LANG_CODE)


def get_system_lang_code() -> str:
    return os.environ.get("TG_SYSTEM_LANG_CODE", _DEFAULT_SYSTEM_LANG_CODE)


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
