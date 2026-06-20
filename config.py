from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _path_from_env(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _int_from_env(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw.isdigit():
        return None

    value = int(raw)
    return value if value > 0 else None


def _id_set_from_env(name: str) -> set[int]:
    ids: set[int] = set()
    raw = os.getenv(name, "")
    for item in raw.replace(";", ",").split(","):
        cleaned = item.strip()
        if cleaned.isdigit():
            ids.add(int(cleaned))
    return ids


BRAND_NAME = "Master SYNC"
FOOTER_TEXT = "Master SYNC"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "/").strip() or "/"
BOT_GUILD_ID = _int_from_env("BOT_GUILD_ID")
OWNER_ID = _int_from_env("OWNER_ID")
GLOBAL_ADMIN_IDS = _id_set_from_env("GLOBAL_ADMIN_IDS")
if OWNER_ID:
    GLOBAL_ADMIN_IDS.add(OWNER_ID)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

DATABASE_PATH = _path_from_env("DATABASE_PATH", "data/mastersync.sqlite3")
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"
COGS_DIR = PROJECT_ROOT / "cogs"
ASSETS_DIR = PROJECT_ROOT / "assets"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOGS_DIR / "mastersync.log"

WELCOME_BG_PATH = ASSETS_DIR / "welcome_bg.png"
DEFAULT_AVATAR_PATH = ASSETS_DIR / "default_avatar.png"
BRAND_LOGO_PATH = ASSETS_DIR / "mastersync_logo.png"
BRAND_BANNER_PATH = ASSETS_DIR / "mastersync_banner.png"

CURRENCY_NAME = "MasterCoins"
CURRENCY_SYMBOL = "M$"

EMBED_COLOR = 0x7C3AED
BLUE_COLOR = 0x2563EB
SUCCESS_COLOR = 0x22C55E
ERROR_COLOR = 0xEF4444
WARNING_COLOR = 0xF59E0B

DAILY_REWARD_MIN = 250
DAILY_REWARD_MAX = 750
WORK_REWARD_MIN = 80
WORK_REWARD_MAX = 350
DAILY_COOLDOWN_SECONDS = 24 * 60 * 60
WORK_COOLDOWN_SECONDS = 60 * 60

MIN_BET = 10
MAX_BET = 50_000

SUBSCRIPTION_BLOCK_MESSAGE = (
    "A assinatura deste servidor esta inativa. Entre em contato com o responsavel "
    "pelo Master SYNC para renovar o acesso."
)


def ensure_runtime_dirs() -> None:
    for directory in (ASSETS_DIR, DATA_DIR, LOGS_DIR, DATABASE_PATH.parent):
        directory.mkdir(parents=True, exist_ok=True)


def is_global_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id in GLOBAL_ADMIN_IDS)
