from __future__ import annotations

from pathlib import Path
from typing import Iterable

import discord

from config import EMBED_COLOR, FOOTER_TEXT
from utils.icon_map import DEFAULT_FOOTER_ICON, ICON_MAP
from utils.icons import ICONS_DIR


def _icon_path(icon_name: str | Path | None) -> Path | None:
    if icon_name is None:
        return None

    if isinstance(icon_name, Path):
        path = icon_name
    else:
        filename = ICON_MAP.get(icon_name, icon_name)
        path = Path(filename)

    if not path.is_absolute():
        path = ICONS_DIR / path
    return path if path.is_file() else None


def get_icon_attachment_url(icon_name: str | Path | None) -> str | None:
    path = _icon_path(icon_name)
    return f"attachment://{path.name}" if path else None


def get_icon_file(icon_name: str | Path | None) -> discord.File | None:
    path = _icon_path(icon_name)
    if path is None:
        return None
    return discord.File(str(path), filename=path.name)


def _unique_files(files: Iterable[discord.File | None]) -> list[discord.File]:
    seen: set[str] = set()
    result: list[discord.File] = []
    for file in files:
        if file is None or file.filename in seen:
            continue
        seen.add(file.filename)
        result.append(file)
    return result


def _files_kwargs(files: Iterable[discord.File | None]) -> dict[str, list[discord.File]]:
    prepared = _unique_files(files)
    return {"files": prepared} if prepared else {}


def files_kwargs(files: Iterable[discord.File | None]) -> dict[str, list[discord.File]]:
    return _files_kwargs(files)


def decorate_embed_with_icon(
    embed: discord.Embed,
    icon_name: str | Path | None = None,
    *,
    thumbnail: bool = False,
    author_name: str | None = None,
    footer_text: str | None = FOOTER_TEXT,
    footer_icon_name: str | Path | None = DEFAULT_FOOTER_ICON,
) -> list[discord.File]:
    files: list[discord.File | None] = []

    icon_url = get_icon_attachment_url(icon_name)
    if icon_url and thumbnail:
        embed.set_thumbnail(url=icon_url)
        files.append(get_icon_file(icon_name))

    if author_name:
        if icon_url:
            embed.set_author(name=author_name, icon_url=icon_url)
            files.append(get_icon_file(icon_name))
        else:
            embed.set_author(name=author_name)

    if footer_text is not None:
        footer_url = get_icon_attachment_url(footer_icon_name)
        if footer_url:
            embed.set_footer(text=footer_text, icon_url=footer_url)
            files.append(get_icon_file(footer_icon_name))
        else:
            embed.set_footer(text=footer_text)

    return _unique_files(files)


def create_embed(
    title: str,
    description: str | None = None,
    *,
    icon_name: str | Path | None = None,
    color: int | None = None,
    author_name: str | None = None,
    thumbnail: bool = False,
    footer_icon_name: str | Path | None = DEFAULT_FOOTER_ICON,
    timestamp: bool = True,
) -> discord.Embed:
    created = discord.utils.utcnow() if timestamp else None
    embed = discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR if color is None else color,
        timestamp=created,
    )
    if author_name:
        embed.set_author(name=author_name)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


async def send_embed_with_icon(
    interaction: discord.Interaction,
    embed: discord.Embed,
    icon_name: str | Path | None = None,
    *,
    ephemeral: bool = False,
    thumbnail: bool = False,
    author_name: str | None = None,
    footer_icon_name: str | Path | None = DEFAULT_FOOTER_ICON,
) -> None:
    footer_text = getattr(embed.footer, "text", None) or FOOTER_TEXT
    files = decorate_embed_with_icon(
        embed,
        icon_name,
        thumbnail=thumbnail,
        author_name=author_name,
        footer_text=footer_text,
        footer_icon_name=footer_icon_name,
    )
    kwargs = _files_kwargs(files)

    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=ephemeral, **kwargs)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral, **kwargs)


async def send_channel_embed_with_icon(
    channel: discord.abc.Messageable,
    embed: discord.Embed,
    icon_name: str | Path | None = None,
    *,
    thumbnail: bool = False,
    author_name: str | None = None,
    footer_icon_name: str | Path | None = DEFAULT_FOOTER_ICON,
) -> None:
    footer_text = getattr(embed.footer, "text", None) or FOOTER_TEXT
    files = decorate_embed_with_icon(
        embed,
        icon_name,
        thumbnail=thumbnail,
        author_name=author_name,
        footer_text=footer_text,
        footer_icon_name=footer_icon_name,
    )
    await channel.send(embed=embed, **_files_kwargs(files))
