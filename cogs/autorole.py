from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, info, respond, success
from database.db import utc_now_iso
from utils.checks import premium_required


class Autorole(commands.Cog):
    autorole = app_commands.Group(name="autorole", description="Cargos automaticos e cargos por painel.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if not self.bot.db.feature_enabled(member.guild.id, "autorole"):
            return
        settings = self.bot.config_service.get_guild_config(member.guild.id)
        if not settings["autorole_enabled"]:
            return
        rows = self.bot.db.fetchall("SELECT role_id FROM autoroles WHERE guild_id = ? AND mode = 'join'", (member.guild.id,))
        if settings["autorole_delay"]:
            await asyncio.sleep(int(settings["autorole_delay"]))
        role_ids = {int(row["role_id"]) for row in rows}
        if settings.get("autorole_role_id"):
            role_ids.add(int(settings["autorole_role_id"]))
        roles = [member.guild.get_role(role_id) for role_id in role_ids]
        roles = [role for role in roles if role is not None]
        if roles:
            try:
                await member.add_roles(*roles, reason="Autorole Master SYNC")
            except discord.HTTPException:
                pass

    @autorole.command(name="configurar", description="Ativa ou desativa autorole e define delay.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    @premium_required
    async def configure(self, interaction: discord.Interaction, ativo: bool, delay_segundos: app_commands.Range[int, 0, 3600] = 0) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "autorole_enabled", 1 if ativo else 0)
        self.bot.db.update_guild_setting(interaction.guild_id, "autorole_delay", int(delay_segundos))
        await respond(interaction, success("Autorole configurado", f"Autorole {'ativo' if ativo else 'inativo'} com delay de {delay_segundos}s."), ephemeral=True, icon_name="user", thumbnail=True)

    @autorole.command(name="adicionar", description="Adiciona um cargo automatico.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    @premium_required
    async def add(self, interaction: discord.Interaction, cargo: discord.Role) -> None:
        self.bot.db.execute(
            "INSERT OR IGNORE INTO autoroles (guild_id, role_id, mode, label, created_at) VALUES (?, ?, 'join', ?, ?)",
            (interaction.guild_id, cargo.id, cargo.name, utc_now_iso()),
        )
        self.bot.db.update_guild_setting(interaction.guild_id, "autorole_enabled", 1)
        await respond(interaction, success("Cargo adicionado", f"{cargo.mention} sera entregue ao entrar."), ephemeral=True, icon_name="user", thumbnail=True)

    @autorole.command(name="remover", description="Remove um cargo automatico.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    @premium_required
    async def remove(self, interaction: discord.Interaction, cargo: discord.Role) -> None:
        self.bot.db.execute("DELETE FROM autoroles WHERE guild_id = ? AND role_id = ? AND mode = 'join'", (interaction.guild_id, cargo.id))
        await respond(interaction, success("Cargo removido", f"{cargo.mention} foi removido do autorole."), ephemeral=True, icon_name="user", thumbnail=True)

    @autorole.command(name="listar", description="Lista cargos automaticos configurados.")
    @app_commands.guild_only()
    @premium_required
    async def list_roles(self, interaction: discord.Interaction) -> None:
        rows = self.bot.db.fetchall("SELECT role_id FROM autoroles WHERE guild_id = ? AND mode = 'join'", (interaction.guild_id,))
        mentions = []
        for row in rows:
            role = interaction.guild.get_role(row["role_id"])
            if role:
                mentions.append(role.mention)
        await respond(interaction, info("Autoroles", "\n".join(mentions) if mentions else "Nenhum cargo configurado."), ephemeral=True, icon_name="user", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Autorole(bot))
