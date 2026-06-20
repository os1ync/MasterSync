from __future__ import annotations

from collections.abc import Callable
from typing import Any

import discord
from discord import app_commands

import config
from cogs._helpers import error, respond


async def _send_block(interaction: discord.Interaction) -> None:
    await respond(interaction, error("Assinatura inativa", config.SUBSCRIPTION_BLOCK_MESSAGE), ephemeral=True, icon_name="error", thumbnail=True)


def owner_only(func: Callable[..., Any] | None = None):
    async def predicate(interaction: discord.Interaction) -> bool:
        if config.is_global_admin(interaction.user.id):
            return True
        await respond(interaction, error("Acesso restrito", "Apenas administradores globais do Master SYNC podem usar este comando."), ephemeral=True)
        return False

    decorator = app_commands.check(predicate)
    return decorator if func is None else decorator(func)


def premium_required(func: Callable[..., Any] | None = None):
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild_id is None:
            await respond(interaction, error("Servidor obrigatorio", "Este comando precisa ser usado em um servidor."), ephemeral=True)
            return False
        if config.is_global_admin(interaction.user.id):
            return True
        if interaction.client.db.is_subscription_active(interaction.guild_id):
            return True
        await _send_block(interaction)
        return False

    decorator = app_commands.check(predicate)
    return decorator if func is None else decorator(func)


def feature_required(feature: str):
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild_id is None:
            await respond(interaction, error("Servidor obrigatorio", "Este comando precisa ser usado em um servidor."), ephemeral=True)
            return False
        if config.is_global_admin(interaction.user.id):
            return True
        if interaction.client.db.feature_enabled(interaction.guild_id, feature):
            return True
        await _send_block(interaction)
        return False

    return app_commands.check(predicate)
