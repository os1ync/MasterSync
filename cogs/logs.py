from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import info, respond, send_log, success
from utils.checks import premium_required


class Logs(commands.Cog):
    logs = app_commands.Group(name="logs", description="Configuracao e eventos de logs do Master SYNC.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def dispatch_log(self, guild: discord.Guild, title: str, description: str) -> None:
        if not self.bot.db.feature_enabled(guild.id, "logs"):
            return
        settings = self.bot.config_service.get_guild_config(guild.id)
        if not settings["logs_enabled"]:
            return
        await send_log(self.bot, guild, info(title, description), icon_name="shield")

    @logs.command(name="configurar", description="Define o canal de logs.")
    @app_commands.describe(canal="Canal que recebera os logs.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def configure(self, interaction: discord.Interaction, canal: discord.TextChannel) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "logs_channel_id", canal.id)
        await respond(interaction, success("Logs configurados", f"Os logs serao enviados em {canal.mention}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @logs.command(name="ativar", description="Ativa os logs do servidor.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def enable(self, interaction: discord.Interaction) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "logs_enabled", 1)
        await respond(interaction, success("Logs ativados", "O sistema de logs foi ativado."), ephemeral=True, icon_name="shield", thumbnail=True)

    @logs.command(name="desativar", description="Desativa os logs do servidor.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def disable(self, interaction: discord.Interaction) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "logs_enabled", 0)
        await respond(interaction, success("Logs desativados", "O sistema de logs foi desativado."), ephemeral=True, icon_name="shield", thumbnail=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        settings = self.bot.config_service.get_guild_config(member.guild.id)
        if not settings.get("log_member_join", 1):
            return
        await self.dispatch_log(member.guild, "Membro entrou", f"{member.mention} entrou no servidor. ID: `{member.id}`")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        settings = self.bot.config_service.get_guild_config(member.guild.id)
        if not settings.get("log_member_leave", 1):
            return
        await self.dispatch_log(member.guild, "Membro saiu", f"{member} saiu do servidor. ID: `{member.id}`")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        settings = self.bot.config_service.get_guild_config(message.guild.id)
        if not settings.get("log_message_delete", 1):
            return
        content = message.content[:800] if message.content else "Sem conteudo textual."
        await self.dispatch_log(message.guild, "Mensagem apagada", f"Autor: {message.author.mention}\nCanal: {message.channel.mention}\nConteudo: {content}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not before.guild or before.author.bot or before.content == after.content:
            return
        settings = self.bot.config_service.get_guild_config(before.guild.id)
        if not settings.get("log_message_edit", 1):
            return
        await self.dispatch_log(before.guild, "Mensagem editada", f"Autor: {before.author.mention}\nCanal: {before.channel.mention}\nAntes: {before.content[:400]}\nDepois: {after.content[:400]}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await self.dispatch_log(channel.guild, "Canal criado", f"Canal: {channel.mention if hasattr(channel, 'mention') else channel.name}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await self.dispatch_log(channel.guild, "Canal deletado", f"Canal: {channel.name}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        await self.dispatch_log(role.guild, "Cargo criado", f"Cargo: {role.mention}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self.dispatch_log(role.guild, "Cargo deletado", f"Cargo: {role.name}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.nick != after.nick:
            await self.dispatch_log(after.guild, "Nickname alterado", f"Usuario: {after.mention}\nAntes: {before.nick or before.name}\nDepois: {after.nick or after.name}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Logs(bot))
