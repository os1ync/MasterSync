from __future__ import annotations

import random
import re
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs._helpers import error, info, respond, success
from database.db import utc_now_iso
from utils.checks import feature_required
from utils.embed_factory import decorate_embed_with_icon, files_kwargs
from utils.formatters import discord_time


def parse_duration(raw: str) -> timedelta:
    match = re.fullmatch(r"(\d+)([mhd])", raw.strip().lower())
    if not match:
        raise ValueError("Use formatos como 30m, 2h ou 7d.")
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(days=value)


class GiveawayView(discord.ui.View):
    def __init__(self, bot: commands.Bot, giveaway_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="Participar", style=discord.ButtonStyle.primary, custom_id="mastersync:giveaway:join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        row = self.bot.db.fetchone("SELECT * FROM giveaways WHERE id = ?", (self.giveaway_id,))
        if row is None or row["status"] != "active":
            await respond(interaction, error("Sorteio encerrado", "Este sorteio nao esta mais ativo."), ephemeral=True)
            return
        self.bot.db.execute(
            "INSERT OR IGNORE INTO giveaway_entries (giveaway_id, user_id, created_at) VALUES (?, ?, ?)",
            (self.giveaway_id, interaction.user.id, utc_now_iso()),
        )
        await respond(interaction, success("Participacao registrada", "Voce esta participando do sorteio."), ephemeral=True, icon_name="success", thumbnail=True)


class Giveaways(commands.Cog):
    sorteio = app_commands.Group(name="sorteio", description="Sistema de sorteios do Master SYNC.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.finish_giveaways.start()

    def cog_unload(self) -> None:
        self.finish_giveaways.cancel()

    async def finish_one(self, row) -> None:
        guild = self.bot.get_guild(row["guild_id"])
        channel = guild.get_channel(row["channel_id"]) if guild else None
        entries = self.bot.db.fetchall("SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?", (row["id"],))
        winners = random.sample(entries, k=min(len(entries), row["winners"])) if entries else []
        winner_text = ", ".join(f"<@{w['user_id']}>" for w in winners) if winners else "Nenhum participante valido."
        self.bot.db.execute("UPDATE giveaways SET status = 'ended' WHERE id = ?", (row["id"],))
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=info("Sorteio encerrado", f"Premio: **{row['prize']}**\nVencedores: {winner_text}"))

    @tasks.loop(minutes=1)
    async def finish_giveaways(self) -> None:
        rows = self.bot.db.fetchall(
            "SELECT * FROM giveaways WHERE status = 'active' AND datetime(ends_at) <= datetime('now')"
        )
        for row in rows:
            await self.finish_one(row)

    @finish_giveaways.before_loop
    async def before_finish_giveaways(self) -> None:
        await self.bot.wait_until_ready()

    @sorteio.command(name="criar", description="Cria um sorteio com botao de participacao.")
    @app_commands.describe(premio="Premio do sorteio.", duracao="Duracao: 30m, 2h ou 7d.", vencedores="Numero de vencedores.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("giveaways")
    async def create(self, interaction: discord.Interaction, premio: str, duracao: str, vencedores: app_commands.Range[int, 1, 20] = 1) -> None:
        settings = self.bot.db.get_guild_settings(interaction.guild_id)
        if not settings["giveaways_enabled"]:
            await respond(interaction, error("Sorteios desativados", "O sistema de sorteios esta desativado neste servidor."), ephemeral=True)
            return
        subscription = self.bot.db.get_subscription(interaction.guild_id)
        max_giveaways = int(subscription["max_giveaways"] or 0) if subscription else 0
        active = self.bot.db.fetchone(
            "SELECT COUNT(*) AS total FROM giveaways WHERE guild_id = ? AND status = 'active'",
            (interaction.guild_id,),
        )
        if max_giveaways and active and active["total"] >= max_giveaways:
            await respond(interaction, error("Limite de sorteios atingido", "O plano atual atingiu o limite de sorteios ativos."), ephemeral=True)
            return
        try:
            delta = parse_duration(duracao)
        except ValueError as exc:
            await respond(interaction, error("Duracao invalida", str(exc)), ephemeral=True)
            return
        ends_at = (discord.utils.utcnow() + delta).isoformat()
        self.bot.db.execute(
            "INSERT INTO giveaways (guild_id, channel_id, prize, winners, ends_at, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (interaction.guild_id, interaction.channel_id, premio[:200], int(vencedores), ends_at, interaction.user.id, utc_now_iso()),
        )
        row = self.bot.db.fetchone("SELECT * FROM giveaways WHERE guild_id = ? ORDER BY id DESC LIMIT 1", (interaction.guild_id,))
        embed = info("Sorteio", f"Premio: **{premio}**\nVencedores: **{vencedores}**\nTermina: {discord_time(ends_at, 'R')}")
        files = decorate_embed_with_icon(embed, "ranking", thumbnail=True, author_name="Sorteios")
        await interaction.response.send_message(embed=embed, view=GiveawayView(self.bot, row["id"]), **files_kwargs(files))
        message = await interaction.original_response()
        self.bot.db.execute("UPDATE giveaways SET message_id = ? WHERE id = ?", (message.id, row["id"]))

    @sorteio.command(name="reroll", description="Sorteia novamente os vencedores de um sorteio encerrado.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("giveaways")
    async def reroll(self, interaction: discord.Interaction, sorteio_id: int) -> None:
        row = self.bot.db.fetchone("SELECT * FROM giveaways WHERE id = ? AND guild_id = ?", (sorteio_id, interaction.guild_id))
        if row is None:
            await respond(interaction, error("Sorteio nao encontrado", "Confira o ID informado."), ephemeral=True)
            return
        entries = self.bot.db.fetchall("SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?", (sorteio_id,))
        if not entries:
            await respond(interaction, error("Sem participantes", "Nao ha participantes para sortear."), ephemeral=True)
            return
        winners = random.sample(entries, k=min(len(entries), row["winners"]))
        await respond(interaction, success("Reroll concluido", "Novos vencedores: " + ", ".join(f"<@{w['user_id']}>" for w in winners)), icon_name="ranking", thumbnail=True)

    @sorteio.command(name="cancelar", description="Cancela um sorteio ativo.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("giveaways")
    async def cancel(self, interaction: discord.Interaction, sorteio_id: int) -> None:
        self.bot.db.execute("UPDATE giveaways SET status = 'cancelled' WHERE id = ? AND guild_id = ?", (sorteio_id, interaction.guild_id))
        await respond(interaction, success("Sorteio cancelado", f"O sorteio `{sorteio_id}` foi cancelado."), ephemeral=True, icon_name="warning", thumbnail=True)

    @sorteio.command(name="listar", description="Lista sorteios ativos.")
    @app_commands.guild_only()
    @feature_required("giveaways")
    async def list_active(self, interaction: discord.Interaction) -> None:
        rows = self.bot.db.fetchall("SELECT * FROM giveaways WHERE guild_id = ? AND status = 'active' ORDER BY ends_at ASC", (interaction.guild_id,))
        lines = [f"`{r['id']}` - {r['prize']} - termina {discord_time(r['ends_at'], 'R')}" for r in rows[:15]]
        await respond(interaction, info("Sorteios ativos", "\n".join(lines) if lines else "Nenhum sorteio ativo."), ephemeral=True, icon_name="ranking", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaways(bot))
