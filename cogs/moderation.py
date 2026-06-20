from __future__ import annotations

from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, info, respond, send_log, success


def default_reason(reason: str | None) -> str:
    return reason.strip() if reason and reason.strip() else "Sem motivo informado"


def hierarchy_allows(actor: discord.Member, target: discord.Member) -> bool:
    if actor.guild.owner_id == actor.id:
        return True
    return actor.top_role > target.top_role


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def mod_log(
        self,
        guild: discord.Guild,
        title: str,
        moderator: discord.abc.User,
        target: discord.abc.User | None,
        reason: str,
    ) -> None:
        message = info(title)
        if target:
            message.add_field(name="Usuário", value=f"{target.mention} (`{target.id}`)", inline=False)
        message.add_field(name="Moderador", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
        message.add_field(name="Motivo", value=reason, inline=False)
        await send_log(self.bot, guild, message, icon_name="shield")

    async def validate_target(self, interaction: discord.Interaction, target: discord.Member) -> bool:
        actor = interaction.user
        bot_member = interaction.guild.me
        if target.id == interaction.guild.owner_id:
            await respond(interaction, error("Acao bloqueada", "Nao posso moderar o dono do servidor."), ephemeral=True)
            return False
        if isinstance(actor, discord.Member) and not hierarchy_allows(actor, target):
            await respond(interaction, error("Hierarquia insuficiente", "Seu cargo precisa estar acima do cargo do usuario."), ephemeral=True)
            return False
        if bot_member and not hierarchy_allows(bot_member, target):
            await respond(interaction, error("Hierarquia do bot insuficiente", "Meu cargo precisa estar acima do cargo do usuario."), ephemeral=True)
            return False
        return True

    @app_commands.command(name="ban", description="Bane um usuário do servidor.")
    @app_commands.describe(usuario="Usuário que será banido.", motivo="Motivo do banimento.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sem motivo informado") -> None:
        reason = default_reason(motivo)
        if not await self.validate_target(interaction, usuario):
            return
        await usuario.ban(reason=f"{reason} | Moderador: {interaction.user} ({interaction.user.id})")
        await respond(interaction, success("Usuario banido", f"{usuario.mention} foi banido.\nMotivo: **{reason}**"), icon_name="shield", thumbnail=True)
        await self.mod_log(interaction.guild, "Banimento aplicado", interaction.user, usuario, reason)

    @app_commands.command(name="unban", description="Remove banimento de um usuario pelo ID.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, usuario_id: str, motivo: str = "Sem motivo informado") -> None:
        if not usuario_id.isdigit():
            await respond(interaction, error("ID invalido", "Informe um ID numerico."), ephemeral=True)
            return
        user = discord.Object(id=int(usuario_id))
        reason = default_reason(motivo)
        await interaction.guild.unban(user, reason=f"{reason} | Moderador: {interaction.user} ({interaction.user.id})")
        await respond(interaction, success("Usuario desbanido", f"O ID `{usuario_id}` foi desbanido.\nMotivo: **{reason}**"), icon_name="shield", thumbnail=True)

    @app_commands.command(name="kick", description="Expulsa um usuário do servidor.")
    @app_commands.describe(usuario="Usuário que será expulso.", motivo="Motivo da expulsão.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sem motivo informado") -> None:
        reason = default_reason(motivo)
        if not await self.validate_target(interaction, usuario):
            return
        await usuario.kick(reason=f"{reason} | Moderador: {interaction.user} ({interaction.user.id})")
        await respond(interaction, success("Usuario expulso", f"{usuario.mention} foi expulso.\nMotivo: **{reason}**"), icon_name="shield", thumbnail=True)
        await self.mod_log(interaction.guild, "Expulsao aplicada", interaction.user, usuario, reason)

    @app_commands.command(name="timeout", description="Coloca um usuário em timeout.")
    @app_commands.describe(usuario="Usuário que receberá timeout.", minutos="Duração em minutos.", motivo="Motivo do timeout.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        minutos: app_commands.Range[int, 1, 40320],
        motivo: str = "Sem motivo informado",
    ) -> None:
        reason = default_reason(motivo)
        if not await self.validate_target(interaction, usuario):
            return
        until = discord.utils.utcnow() + timedelta(minutes=int(minutos))
        await usuario.timeout(until, reason=f"{reason} | Moderador: {interaction.user} ({interaction.user.id})")
        await respond(interaction, success("Timeout aplicado", f"{usuario.mention} recebeu timeout por **{minutos} minuto(s)**.\nMotivo: **{reason}**"), icon_name="shield", thumbnail=True)
        await self.mod_log(interaction.guild, "Timeout aplicado", interaction.user, usuario, reason)

    @app_commands.command(name="untimeout", description="Remove timeout de um usuario.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sem motivo informado") -> None:
        if not await self.validate_target(interaction, usuario):
            return
        reason = default_reason(motivo)
        await usuario.timeout(None, reason=f"{reason} | Moderador: {interaction.user} ({interaction.user.id})")
        await respond(interaction, success("Timeout removido", f"Timeout removido de {usuario.mention}."), icon_name="shield", thumbnail=True)

    @app_commands.command(name="warn", description="Registra um aviso em um usuario.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sem motivo informado") -> None:
        reason = default_reason(motivo)
        warning_id = self.bot.db.add_warning(interaction.guild_id, usuario.id, interaction.user.id, reason)
        await respond(interaction, success("Aviso registrado", f"Aviso `{warning_id}` registrado para {usuario.mention}.\nMotivo: **{reason}**"), icon_name="shield", thumbnail=True)
        await self.mod_log(interaction.guild, "Aviso registrado", interaction.user, usuario, reason)

    @app_commands.command(name="warnings", description="Lista avisos de um usuario.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        rows = self.bot.db.get_warnings(interaction.guild_id, usuario.id)
        lines = [f"`{row['id']}` - {row['reason']} - <@{row['moderator_id']}>" for row in rows[:10]]
        await respond(interaction, success("Avisos do usuario", "\n".join(lines) if lines else "Nenhum aviso registrado."), ephemeral=True, icon_name="shield", thumbnail=True)

    @app_commands.command(name="clearwarnings", description="Remove todos os avisos de um usuario.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def clearwarnings(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        total = self.bot.db.clear_warnings(interaction.guild_id, usuario.id)
        await respond(interaction, success("Avisos removidos", f"Foram removidos **{total}** avisos de {usuario.mention}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @app_commands.command(name="limpar", description="Apaga mensagens recentes do canal.")
    @app_commands.describe(quantidade="Quantidade de mensagens para apagar, entre 1 e 100.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, quantidade: app_commands.Range[int, 1, 100]) -> None:
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await respond(interaction, error("Canal invalido", "Use este comando em um canal de texto."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted = await channel.purge(
            limit=int(quantidade),
            reason=f"Limpeza solicitada por {interaction.user} ({interaction.user.id})",
        )
        await respond(interaction, success("Limpeza concluida", f"Foram apagadas **{len(deleted)}** mensagens."), ephemeral=True, icon_name="shield", thumbnail=True)
        await self.mod_log(interaction.guild, "Mensagens apagadas", interaction.user, None, f"{len(deleted)} mensagens em {channel.mention}")

    @app_commands.command(name="lock", description="Bloqueia o envio de mensagens no canal atual.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await respond(interaction, error("Canal invalido", "Use este comando em um canal de texto."), ephemeral=True)
            return

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Canal bloqueado por {interaction.user} ({interaction.user.id})",
        )
        await respond(interaction, success("Canal bloqueado", f"{channel.mention} foi bloqueado."), icon_name="shield", thumbnail=True)
        await self.mod_log(interaction.guild, "Canal bloqueado", interaction.user, None, channel.mention)

    @app_commands.command(name="unlock", description="Libera o envio de mensagens no canal atual.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await respond(interaction, error("Canal invalido", "Use este comando em um canal de texto."), ephemeral=True)
            return

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Canal liberado por {interaction.user} ({interaction.user.id})",
        )
        await respond(interaction, success("Canal liberado", f"{channel.mention} foi liberado."), icon_name="shield", thumbnail=True)
        await self.mod_log(interaction.guild, "Canal liberado", interaction.user, None, channel.mention)

    @app_commands.command(name="slowmode", description="Define modo lento no canal atual.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, segundos: app_commands.Range[int, 0, 21600]) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await respond(interaction, error("Canal invalido", "Use este comando em um canal de texto."), ephemeral=True)
            return
        await interaction.channel.edit(slowmode_delay=int(segundos), reason=f"Slowmode por {interaction.user} ({interaction.user.id})")
        await respond(interaction, success("Slowmode atualizado", f"Modo lento definido para **{segundos}** segundos."), icon_name="shield", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
