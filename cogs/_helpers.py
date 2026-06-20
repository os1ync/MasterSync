from __future__ import annotations

from datetime import datetime, timezone

import discord

from config import (
    BLUE_COLOR,
    CURRENCY_SYMBOL,
    EMBED_COLOR,
    ERROR_COLOR,
    FOOTER_TEXT,
    SUCCESS_COLOR,
    WARNING_COLOR,
)
from utils.embed_factory import create_embed, send_channel_embed_with_icon, send_embed_with_icon


def money(amount: int) -> str:
    formatted = f"{amount:,}".replace(",", ".")
    return f"{CURRENCY_SYMBOL} {formatted}"


def human_delta(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}min")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def unix_timestamp(value: str | None) -> int | None:
    parsed = parse_iso(value)
    return int(parsed.timestamp()) if parsed else None


def embed(
    title: str,
    description: str | None = None,
    *,
    color: int = EMBED_COLOR,
    timestamp: bool = True,
) -> discord.Embed:
    return create_embed(title, description, color=color, timestamp=timestamp)


def success(title: str, description: str | None = None) -> discord.Embed:
    return create_embed(title, description, icon_name="success", color=SUCCESS_COLOR)


def error(title: str, description: str | None = None) -> discord.Embed:
    return create_embed(title, description, icon_name="error", color=ERROR_COLOR)


def warning(title: str, description: str | None = None) -> discord.Embed:
    return create_embed(title, description, icon_name="warning", color=WARNING_COLOR)


def info(title: str, description: str | None = None) -> discord.Embed:
    return create_embed(title, description, icon_name="info", color=BLUE_COLOR)


async def respond(
    interaction: discord.Interaction,
    message: discord.Embed,
    *,
    ephemeral: bool = False,
    icon=None,
    icon_name=None,
    thumbnail: bool = False,
    author_name: str | None = None,
    footer_icon: bool = True,
) -> None:
    color_value = message.color.value if message.color else None
    selected_icon = icon_name or icon
    if selected_icon is None:
        if color_value == ERROR_COLOR:
            selected_icon = "error"
        elif color_value == SUCCESS_COLOR:
            selected_icon = "success"
        elif color_value == WARNING_COLOR:
            selected_icon = "warning"
        elif color_value == BLUE_COLOR:
            selected_icon = "info"
    thumbnail = thumbnail or selected_icon in {"error", "warning"}
    footer_icon_name = "info" if footer_icon else None
    await send_embed_with_icon(
        interaction,
        message,
        selected_icon,
        ephemeral=ephemeral,
        thumbnail=thumbnail,
        author_name=author_name,
        footer_icon_name=footer_icon_name,
    )


async def send_log(
    bot: discord.Client,
    guild: discord.Guild,
    message: discord.Embed,
    *,
    icon=None,
    icon_name=None,
) -> None:
    if not hasattr(bot, "db"):
        return
    settings = bot.db.get_guild_settings(guild.id)
    channel_id = settings["logs_channel_id"]
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        try:
            await send_channel_embed_with_icon(channel, message, icon_name or icon or "shield")
        except discord.HTTPException:
            return
