from __future__ import annotations

from pathlib import Path
from typing import Iterable

import discord

from config import ASSETS_DIR, FOOTER_TEXT
from utils.icon_map import ICON_MAP


ICONS_DIR = ASSETS_DIR / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

COINS_ICON = ICONS_DIR / "coins.png"
CASINO_ICON = ICONS_DIR / "casino.png"
DICE_ICON = ICONS_DIR / "dice.png"
SLOT_ICON = ICONS_DIR / "slot.png"
WELCOME_ICON = ICONS_DIR / "welcome.png"
SHIELD_ICON = ICONS_DIR / "shield.png"
USER_ICON = ICONS_DIR / "user.png"
WARNING_ICON = ICONS_DIR / "warning.png"
BANK_ICON = ICONS_DIR / "bank.png"
RANKING_ICON = ICONS_DIR / "ranking.png"
WORK_ICON = ICONS_DIR / "work.png"
DAILY_ICON = ICONS_DIR / "daily.png"
SUCCESS_ICON = ICONS_DIR / "success.png"
SETTINGS_ICON = ICONS_DIR / "settings.png"
INFO_ICON = ICONS_DIR / "info.png"


def resolve_icon(icon: Path | str | None) -> Path | None:
    if icon is None:
        return None
    path = Path(ICON_MAP.get(icon, icon)) if isinstance(icon, str) else Path(icon)
    if not path.is_absolute():
        path = ICONS_DIR / path
    return path if path.is_file() else None


def attachment_url(icon: Path | str | None) -> str | None:
    path = resolve_icon(icon)
    return f"attachment://{path.name}" if path else None


def icon_file(icon: Path | str | None) -> discord.File | None:
    path = resolve_icon(icon)
    if path is None:
        return None
    return discord.File(str(path), filename=path.name)


def unique_files(files: Iterable[discord.File | None]) -> list[discord.File]:
    seen: set[str] = set()
    result: list[discord.File] = []
    for file in files:
        if file is None:
            continue
        filename = getattr(file, "filename", None)
        if not filename or filename in seen:
            continue
        seen.add(filename)
        result.append(file)
    return result


def files_kwargs(files: Iterable[discord.File | None]) -> dict[str, list[discord.File]]:
    prepared = unique_files(files)
    return {"files": prepared} if prepared else {}


def decorate_embed(
    embed: discord.Embed,
    icon: Path | str | None,
    *,
    thumbnail: bool = False,
    author_name: str | None = None,
    footer_text: str | None = FOOTER_TEXT,
    footer_icon: bool = True,
) -> bool:
    """Apply attachment:// URLs to an embed without opening the file."""

    path = resolve_icon(icon)
    url = f"attachment://{path.name}" if path else None
    uses_attachment = False

    if thumbnail and url:
        embed.set_thumbnail(url=url)
        uses_attachment = True

    if author_name:
        if url:
            embed.set_author(name=author_name, icon_url=url)
            uses_attachment = True
        else:
            embed.set_author(name=author_name)

    if footer_text is not None:
        if url and footer_icon:
            embed.set_footer(text=footer_text, icon_url=url)
            uses_attachment = True
        else:
            embed.set_footer(text=footer_text)

    return bool(path and uses_attachment)


def apply_icon(
    embed: discord.Embed,
    icon: Path | str | None,
    *,
    thumbnail: bool = False,
    author_name: str | None = None,
    footer_text: str | None = FOOTER_TEXT,
    footer_icon: bool = True,
) -> list[discord.File]:
    """Attach a local PNG icon to an embed using attachment:// URLs.

    Missing icons are treated as an intentional fallback. The embed keeps working
    normally and no file is attached.
    """

    path = resolve_icon(icon)
    used = decorate_embed(
        embed,
        icon,
        thumbnail=thumbnail,
        author_name=author_name,
        footer_text=footer_text,
        footer_icon=footer_icon,
    )
    if path and used:
        return [discord.File(str(path), filename=path.name)]
    return []
