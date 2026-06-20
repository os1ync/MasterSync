from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, respond, success
from utils.checks import premium_required


class Automod(commands.Cog):
    automod = app_commands.Group(name="automod", description="Moderacao automatica do Master SYNC.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_times: dict[tuple[int, int], deque[float]] = defaultdict(lambda: deque(maxlen=8))

    def settings(self, guild_id: int):
        row = self.bot.db.fetchone("SELECT * FROM automod_settings WHERE guild_id = ?", (guild_id,))
        if row is None:
            self.bot.db.execute("INSERT OR IGNORE INTO automod_settings (guild_id) VALUES (?)", (guild_id,))
            row = self.bot.db.fetchone("SELECT * FROM automod_settings WHERE guild_id = ?", (guild_id,))
        return row

    @staticmethod
    def id_set(raw: str | None) -> set[int]:
        result: set[int] = set()
        for item in (raw or "").split(","):
            item = item.strip()
            if item.isdigit():
                result.add(int(item))
        return result

    def is_whitelisted(self, message: discord.Message, settings) -> bool:
        channel_ids = self.id_set(settings["whitelist_channels"])
        if message.channel.id in channel_ids:
            return True
        if isinstance(message.author, discord.Member):
            role_ids = self.id_set(settings["whitelist_roles"])
            return any(role.id in role_ids for role in message.author.roles)
        return False

    async def punish(self, message: discord.Message, reason: str) -> None:
        settings = self.settings(message.guild.id)
        action = settings["punishment"]
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        if action in {"warn", "timeout", "kick", "ban"}:
            try:
                await message.channel.send(f"{message.author.mention}, mensagem removida pelo automod. Motivo: {reason}", delete_after=8)
            except discord.HTTPException:
                pass
        if isinstance(message.author, discord.Member) and action == "timeout":
            try:
                await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=10), reason=f"Automod: {reason}")
            except discord.HTTPException:
                pass
        if isinstance(message.author, discord.Member) and action == "kick":
            try:
                await message.author.kick(reason=f"Automod: {reason}")
            except discord.HTTPException:
                pass
        if isinstance(message.author, discord.Member) and action == "ban":
            try:
                await message.author.ban(reason=f"Automod: {reason}")
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot or not message.content:
            return
        guild_settings = self.bot.db.get_guild_settings(message.guild.id)
        if not guild_settings["automod_enabled"] or not self.bot.db.feature_enabled(message.guild.id, "automod"):
            return
        settings = self.settings(message.guild.id)
        if self.is_whitelisted(message, settings):
            return
        content = message.content
        lowered = content.lower()

        if settings["anti_link"] and ("http://" in lowered or "https://" in lowered or "discord.gg/" in lowered):
            await self.punish(message, "links nao permitidos")
            return
        words = [w.strip().lower() for w in (settings["banned_words"] or "").split(",") if w.strip()]
        if words and any(word in lowered for word in words):
            await self.punish(message, "palavra bloqueada")
            return
        if settings["anti_caps"] and len(content) >= 12:
            letters = [c for c in content if c.isalpha()]
            if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.75:
                await self.punish(message, "excesso de letras maiusculas")
                return
        if settings["anti_mentions"] and len(message.mentions) >= 6:
            await self.punish(message, "excesso de mencoes")
            return
        if settings["anti_spam"]:
            key = (message.guild.id, message.author.id)
            now = discord.utils.utcnow().timestamp()
            bucket = self.message_times[key]
            bucket.append(now)
            if len(bucket) >= 5 and now - bucket[0] <= 8:
                await self.punish(message, "spam de mensagens")

    @automod.command(name="painel", description="Mostra o status do automod.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def panel(self, interaction: discord.Interaction) -> None:
        settings = self.settings(interaction.guild_id)
        description = (
            f"Anti-link: {settings['anti_link']}\n"
            f"Anti-spam: {settings['anti_spam']}\n"
            f"Anti-caps: {settings['anti_caps']}\n"
            f"Anti-mention: {settings['anti_mentions']}\n"
            f"Punicao: {settings['punishment']}"
        )
        await respond(interaction, success("Automod", description), ephemeral=True, icon_name="shield", thumbnail=True)

    @automod.command(name="antilink", description="Ativa ou desativa anti-link.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def anti_link(self, interaction: discord.Interaction, ativo: bool) -> None:
        self.settings(interaction.guild_id)
        self.bot.db.execute("UPDATE automod_settings SET anti_link = ? WHERE guild_id = ?", (1 if ativo else 0, interaction.guild_id))
        self.bot.db.update_guild_setting(interaction.guild_id, "automod_enabled", 1)
        await respond(interaction, success("Anti-link atualizado", f"Anti-link {'ativo' if ativo else 'inativo'}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @automod.command(name="antispam", description="Ativa ou desativa anti-spam.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def anti_spam(self, interaction: discord.Interaction, ativo: bool) -> None:
        self.settings(interaction.guild_id)
        self.bot.db.execute("UPDATE automod_settings SET anti_spam = ? WHERE guild_id = ?", (1 if ativo else 0, interaction.guild_id))
        self.bot.db.update_guild_setting(interaction.guild_id, "automod_enabled", 1)
        await respond(interaction, success("Anti-spam atualizado", f"Anti-spam {'ativo' if ativo else 'inativo'}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @automod.command(name="anticaps", description="Ativa ou desativa anti-caps.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def anti_caps(self, interaction: discord.Interaction, ativo: bool) -> None:
        self.settings(interaction.guild_id)
        self.bot.db.execute("UPDATE automod_settings SET anti_caps = ? WHERE guild_id = ?", (1 if ativo else 0, interaction.guild_id))
        self.bot.db.update_guild_setting(interaction.guild_id, "automod_enabled", 1)
        await respond(interaction, success("Anti-caps atualizado", f"Anti-caps {'ativo' if ativo else 'inativo'}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @automod.command(name="antimencoes", description="Ativa ou desativa anti-mention spam.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def anti_mentions(self, interaction: discord.Interaction, ativo: bool) -> None:
        self.settings(interaction.guild_id)
        self.bot.db.execute("UPDATE automod_settings SET anti_mentions = ? WHERE guild_id = ?", (1 if ativo else 0, interaction.guild_id))
        self.bot.db.update_guild_setting(interaction.guild_id, "automod_enabled", 1)
        await respond(interaction, success("Anti-mencoes atualizado", f"Anti-mencoes {'ativo' if ativo else 'inativo'}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @automod.command(name="palavroes", description="Define palavras bloqueadas separadas por virgula.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def words(self, interaction: discord.Interaction, palavras: str) -> None:
        self.settings(interaction.guild_id)
        self.bot.db.execute("UPDATE automod_settings SET banned_words = ? WHERE guild_id = ?", (palavras[:1000], interaction.guild_id))
        self.bot.db.update_guild_setting(interaction.guild_id, "automod_enabled", 1)
        await respond(interaction, success("Palavras atualizadas", "Lista de palavras bloqueadas salva."), ephemeral=True, icon_name="shield", thumbnail=True)

    @automod.command(name="punicao", description="Define a punicao automatica do automod.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def punishment(self, interaction: discord.Interaction, acao: Literal["delete", "warn", "timeout", "kick", "ban"]) -> None:
        self.settings(interaction.guild_id)
        self.bot.db.execute("UPDATE automod_settings SET punishment = ? WHERE guild_id = ?", (acao, interaction.guild_id))
        await respond(interaction, success("Punicao atualizada", f"Automod configurado para: **{acao}**."), ephemeral=True, icon_name="shield", thumbnail=True)

    @automod.command(name="whitelist", description="Gerencia whitelist de canal ou cargo.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def whitelist(self, interaction: discord.Interaction, modo: Literal["adicionar", "remover", "limpar"], canal: discord.TextChannel | None = None, cargo: discord.Role | None = None) -> None:
        settings = self.settings(interaction.guild_id)
        if modo == "limpar":
            self.bot.db.execute("UPDATE automod_settings SET whitelist_channels = NULL, whitelist_roles = NULL WHERE guild_id = ?", (interaction.guild_id,))
            await respond(interaction, success("Whitelist limpa", "Canais e cargos foram removidos da whitelist."), ephemeral=True, icon_name="shield", thumbnail=True)
            return
        channel_ids = self.id_set(settings["whitelist_channels"])
        role_ids = self.id_set(settings["whitelist_roles"])
        if canal:
            if modo == "adicionar":
                channel_ids.add(canal.id)
            else:
                channel_ids.discard(canal.id)
        if cargo:
            if modo == "adicionar":
                role_ids.add(cargo.id)
            else:
                role_ids.discard(cargo.id)
        self.bot.db.execute(
            "UPDATE automod_settings SET whitelist_channels = ?, whitelist_roles = ? WHERE guild_id = ?",
            ("".join(f"{item}," for item in sorted(channel_ids)), "".join(f"{item}," for item in sorted(role_ids)), interaction.guild_id),
        )
        action_text = "adicionada a whitelist" if modo == "adicionar" else "removida da whitelist"
        await respond(interaction, success("Whitelist atualizada", f"Entrada {action_text}."), ephemeral=True, icon_name="shield", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Automod(bot))
