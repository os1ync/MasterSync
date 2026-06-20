from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import info, respond, send_log, success
from utils.checks import premium_required


class AntiRaid(commands.Cog):
    antiraid = app_commands.Group(name="antiraid", description="Protecao contra raids.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.joins: dict[int, deque[float]] = defaultdict(lambda: deque(maxlen=50))

    async def set_lockdown(self, guild: discord.Guild, enabled: bool) -> int:
        changed = 0
        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = False if enabled else None
            try:
                await channel.set_permissions(guild.default_role, overwrite=overwrite, reason="Lockdown Master SYNC")
                changed += 1
            except discord.HTTPException:
                continue
        until = (discord.utils.utcnow() + timedelta(minutes=15)).isoformat() if enabled else None
        self.bot.db.execute(
            "INSERT OR IGNORE INTO antiraid_settings (guild_id) VALUES (?)",
            (guild.id,),
        )
        self.bot.db.execute("UPDATE antiraid_settings SET lockdown_until = ? WHERE guild_id = ?", (until, guild.id))
        return changed

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if not self.bot.db.feature_enabled(member.guild.id, "antiraid"):
            return
        row = self.bot.db.fetchone("SELECT * FROM antiraid_settings WHERE guild_id = ?", (member.guild.id,))
        settings = self.bot.db.get_guild_settings(member.guild.id)
        if not settings["antiraid_enabled"] or not row or not row["enabled"]:
            return
        now = discord.utils.utcnow().timestamp()
        bucket = self.joins[member.guild.id]
        bucket.append(now)
        recent = [stamp for stamp in bucket if now - stamp <= row["window_seconds"]]
        if len(recent) >= row["join_limit"]:
            if row["action"] == "kick":
                try:
                    await member.kick(reason="Anti-raid Master SYNC")
                except discord.HTTPException:
                    pass
            else:
                changed = await self.set_lockdown(member.guild, True)
                await send_log(self.bot, member.guild, info("Anti-raid acionado", f"Lockdown aplicado em **{changed}** canais."), icon_name="shield")

    @antiraid.command(name="ativar", description="Ativa o anti-raid.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @premium_required
    async def enable(self, interaction: discord.Interaction) -> None:
        self.bot.db.execute("INSERT OR IGNORE INTO antiraid_settings (guild_id) VALUES (?)", (interaction.guild_id,))
        self.bot.db.execute("UPDATE antiraid_settings SET enabled = 1 WHERE guild_id = ?", (interaction.guild_id,))
        self.bot.db.update_guild_setting(interaction.guild_id, "antiraid_enabled", 1)
        await respond(interaction, success("Anti-raid ativado", "O servidor agora esta monitorando entradas em massa."), ephemeral=True, icon_name="shield", thumbnail=True)

    @antiraid.command(name="desativar", description="Desativa o anti-raid.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @premium_required
    async def disable(self, interaction: discord.Interaction) -> None:
        self.bot.db.execute("INSERT OR IGNORE INTO antiraid_settings (guild_id) VALUES (?)", (interaction.guild_id,))
        self.bot.db.execute("UPDATE antiraid_settings SET enabled = 0 WHERE guild_id = ?", (interaction.guild_id,))
        self.bot.db.update_guild_setting(interaction.guild_id, "antiraid_enabled", 0)
        await respond(interaction, success("Anti-raid desativado", "Monitoramento anti-raid desativado."), ephemeral=True, icon_name="shield", thumbnail=True)

    @antiraid.command(name="configurar", description="Configura limite de entradas e acao.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @premium_required
    async def configure(self, interaction: discord.Interaction, limite: app_commands.Range[int, 2, 50], janela_segundos: app_commands.Range[int, 5, 300], acao: str = "lockdown") -> None:
        action = acao if acao in {"lockdown", "kick"} else "lockdown"
        self.bot.db.execute("INSERT OR IGNORE INTO antiraid_settings (guild_id) VALUES (?)", (interaction.guild_id,))
        self.bot.db.execute("UPDATE antiraid_settings SET join_limit = ?, window_seconds = ?, action = ? WHERE guild_id = ?", (int(limite), int(janela_segundos), action, interaction.guild_id))
        await respond(interaction, success("Anti-raid configurado", f"Limite: {limite} entradas em {janela_segundos}s. Acao: {action}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @app_commands.command(name="lockdown", description="Bloqueia envio de mensagens em todos os canais de texto.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @premium_required
    async def lockdown(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        changed = await self.set_lockdown(interaction.guild, True)
        await respond(interaction, success("Lockdown aplicado", f"Foram bloqueados **{changed}** canais de texto."), ephemeral=True, icon_name="shield", thumbnail=True)

    @app_commands.command(name="unlockdown", description="Remove lockdown dos canais de texto.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @premium_required
    async def unlockdown(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        changed = await self.set_lockdown(interaction.guild, False)
        await respond(interaction, success("Lockdown removido", f"Foram liberados **{changed}** canais de texto."), ephemeral=True, icon_name="shield", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiRaid(bot))
