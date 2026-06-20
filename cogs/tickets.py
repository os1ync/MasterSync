from __future__ import annotations

from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, info, respond, send_log, success
from utils.checks import feature_required
from utils.embed_factory import decorate_embed_with_icon, files_kwargs


class TicketPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Abrir ticket", style=discord.ButtonStyle.primary, custom_id="mastersync:ticket:open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is None:
            return
        settings = self.bot.db.get_guild_settings(interaction.guild.id)
        if not settings["tickets_enabled"]:
            await respond(interaction, error("Tickets desativados", "O sistema de tickets esta desativado neste servidor."), ephemeral=True)
            return
        if not self.bot.db.feature_enabled(interaction.guild.id, "tickets"):
            await respond(interaction, error("Assinatura inativa", "Tickets estao indisponiveis neste servidor."), ephemeral=True)
            return
        subscription = self.bot.db.get_subscription(interaction.guild.id)
        max_tickets = int(subscription["max_tickets"] or 0) if subscription else 0
        open_count = self.bot.db.fetchone(
            "SELECT COUNT(*) AS total FROM tickets WHERE guild_id = ? AND status = 'open'",
            (interaction.guild.id,),
        )
        if max_tickets and open_count and open_count["total"] >= max_tickets:
            await respond(interaction, error("Limite de tickets atingido", "O plano atual atingiu o limite de tickets abertos."), ephemeral=True)
            return
        blocked = self.bot.db.fetchone(
            "SELECT 1 FROM tickets WHERE guild_id = ? AND owner_id = ? AND blocked = 1 LIMIT 1",
            (interaction.guild.id, interaction.user.id),
        )
        if blocked:
            await respond(interaction, error("Ticket bloqueado", "Voce esta bloqueado de abrir tickets neste servidor."), ephemeral=True)
            return
        if self.bot.db.get_open_ticket_for_user(interaction.guild.id, interaction.user.id):
            await respond(interaction, error("Ticket ja aberto", "Voce ja possui um ticket aberto."), ephemeral=True)
            return

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        bot_member = interaction.guild.me
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True)
        support_role_id = settings["ticket_support_role_id"]
        if support_role_id:
            role = interaction.guild.get_role(support_role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        category = interaction.guild.get_channel(settings["ticket_category_id"] or 0)
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}".lower()[:90],
            category=category if isinstance(category, discord.CategoryChannel) else None,
            overwrites=overwrites,
            reason=f"Ticket aberto por {interaction.user} ({interaction.user.id})",
        )
        ticket_id = self.bot.db.create_ticket(interaction.guild.id, interaction.user.id, channel.id, "Painel")
        embed = info("Ticket aberto", f"Ticket `{ticket_id}` criado para {interaction.user.mention}.\nA equipe respondera em breve.")
        files = decorate_embed_with_icon(embed, "shield", thumbnail=True, author_name="Atendimento")
        await channel.send(content=interaction.user.mention, embed=embed, **files_kwargs(files))
        await respond(interaction, success("Ticket criado", f"Seu ticket foi aberto em {channel.mention}."), ephemeral=True, icon_name="shield", thumbnail=True)


class Tickets(commands.Cog):
    ticket = app_commands.Group(name="ticket", description="Sistema premium de tickets.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(TicketPanelView(bot))

    @ticket.command(name="painel", description="Envia o painel de abertura de tickets.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("tickets")
    async def panel(self, interaction: discord.Interaction) -> None:
        embed = info("Atendimento", "Clique no botao para abrir um ticket privado com a equipe.")
        files = decorate_embed_with_icon(embed, "shield", thumbnail=True, author_name="Tickets")
        await interaction.response.send_message(embed=embed, view=TicketPanelView(self.bot), **files_kwargs(files))

    @ticket.command(name="configurar", description="Configura categoria, cargo de suporte e logs de tickets.")
    @app_commands.describe(categoria="Categoria onde tickets serao criados.", cargo="Cargo da equipe de suporte.", logs="Canal de logs de tickets.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("tickets")
    async def configure(self, interaction: discord.Interaction, categoria: discord.CategoryChannel | None = None, cargo: discord.Role | None = None, logs: discord.TextChannel | None = None) -> None:
        if categoria:
            self.bot.db.update_guild_setting(interaction.guild_id, "ticket_category_id", categoria.id)
        if cargo:
            self.bot.db.update_guild_setting(interaction.guild_id, "ticket_support_role_id", cargo.id)
        if logs:
            self.bot.db.update_guild_setting(interaction.guild_id, "ticket_logs_channel_id", logs.id)
        await respond(interaction, success("Tickets configurados", "As configuracoes de tickets foram salvas."), ephemeral=True, icon_name="shield", thumbnail=True)

    async def build_transcript(self, channel: discord.TextChannel) -> str:
        lines = [f"Transcript de #{channel.name}", ""]
        async for message in channel.history(limit=500, oldest_first=True):
            content = message.content or ""
            attachments = " ".join(a.url for a in message.attachments)
            lines.append(f"[{message.created_at.isoformat()}] {message.author}: {content} {attachments}".strip())
        return "\n".join(lines)

    @ticket.command(name="fechar", description="Fecha o ticket atual.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    @feature_required("tickets")
    async def close(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await respond(interaction, error("Canal invalido", "Use este comando dentro de um ticket."), ephemeral=True)
            return
        ticket = self.bot.db.get_ticket_by_channel(interaction.guild_id, interaction.channel.id)
        if ticket is None or ticket["status"] != "open":
            await respond(interaction, error("Ticket nao encontrado", "Este canal nao esta registrado como ticket aberto."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        transcript = await self.build_transcript(interaction.channel)
        self.bot.db.close_ticket(ticket["id"], interaction.user.id, transcript)
        file = discord.File(BytesIO(transcript.encode("utf-8")), filename=f"ticket-{ticket['id']}.txt")
        await interaction.followup.send(content="Ticket fechado. Transcript gerado abaixo.", file=file, ephemeral=True)
        await send_log(self.bot, interaction.guild, info("Ticket fechado", f"Ticket `{ticket['id']}` fechado por {interaction.user.mention}."), icon_name="shield")
        await interaction.channel.delete(reason=f"Ticket fechado por {interaction.user} ({interaction.user.id})")

    @ticket.command(name="assumir", description="Assume o ticket atual.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    @feature_required("tickets")
    async def claim(self, interaction: discord.Interaction) -> None:
        ticket = self.bot.db.get_ticket_by_channel(interaction.guild_id, interaction.channel_id)
        if ticket is None:
            await respond(interaction, error("Ticket nao encontrado", "Este canal nao esta registrado como ticket."), ephemeral=True)
            return
        self.bot.db.claim_ticket(interaction.guild_id, interaction.channel_id, interaction.user.id)
        await respond(interaction, success("Ticket assumido", f"{interaction.user.mention} assumiu este atendimento."), icon_name="shield", thumbnail=True)

    @ticket.command(name="adicionar", description="Adiciona um usuario ao ticket atual.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    @feature_required("tickets")
    async def add_user(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.set_permissions(usuario, view_channel=True, send_messages=True, read_message_history=True)
        await respond(interaction, success("Usuario adicionado", f"{usuario.mention} foi adicionado ao ticket."), ephemeral=True, icon_name="shield", thumbnail=True)

    @ticket.command(name="remover", description="Remove um usuario do ticket atual.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    @feature_required("tickets")
    async def remove_user(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.set_permissions(usuario, overwrite=None)
        await respond(interaction, success("Usuario removido", f"{usuario.mention} foi removido do ticket."), ephemeral=True, icon_name="shield", thumbnail=True)

    @ticket.command(name="transcript", description="Gera transcript do ticket atual.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    @feature_required("tickets")
    async def transcript(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await respond(interaction, error("Canal invalido", "Use este comando em um canal de ticket."), ephemeral=True)
            return
        transcript = await self.build_transcript(interaction.channel)
        file = discord.File(BytesIO(transcript.encode("utf-8")), filename=f"{interaction.channel.name}.txt")
        await interaction.response.send_message(content="Transcript gerado.", file=file, ephemeral=True)

    @ticket.command(name="bloquear", description="Bloqueia um usuario de abrir tickets.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("tickets")
    async def block(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        self.bot.db.execute(
            "INSERT INTO tickets (guild_id, owner_id, status, blocked, reason, created_at) VALUES (?, ?, 'blocked', 1, 'Bloqueio manual', datetime('now'))",
            (interaction.guild_id, usuario.id),
        )
        await respond(interaction, success("Usuario bloqueado", f"{usuario.mention} nao podera abrir tickets."), ephemeral=True, icon_name="shield", thumbnail=True)

    @ticket.command(name="desbloquear", description="Desbloqueia um usuario para abrir tickets.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("tickets")
    async def unblock(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        self.bot.db.execute("DELETE FROM tickets WHERE guild_id = ? AND owner_id = ? AND blocked = 1", (interaction.guild_id, usuario.id))
        await respond(interaction, success("Usuario desbloqueado", f"{usuario.mention} podera abrir tickets novamente."), ephemeral=True, icon_name="shield", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
