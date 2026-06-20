from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, human_delta, money, parse_iso, respond, success, unix_timestamp
import config
from config import (
    CURRENCY_NAME,
    DAILY_COOLDOWN_SECONDS,
    DAILY_REWARD_MAX,
    DAILY_REWARD_MIN,
    EMBED_COLOR,
    WORK_COOLDOWN_SECONDS,
    WORK_REWARD_MAX,
    WORK_REWARD_MIN,
)
from database.db import utc_now_iso


def cooldown_left(last_value: str | None, cooldown_seconds: int) -> int:
    last = parse_iso(last_value)
    if last is None:
        return 0
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return max(0, int(cooldown_seconds - elapsed))


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_enabled(self, interaction: discord.Interaction) -> bool:
        settings = self.bot.db.get_guild_settings(interaction.guild_id)
        if settings["economy_enabled"] and (config.is_global_admin(interaction.user.id) or self.bot.db.feature_enabled(interaction.guild_id, "economy")):
            return True
        await respond(
            interaction,
            error("Economia indisponivel", "A economia esta desativada ou a assinatura nao esta ativa neste servidor."),
            ephemeral=True,
        )
        return False

    @app_commands.command(name="saldo", description="Mostra seu saldo ou o saldo de outro usuário.")
    @app_commands.describe(usuario="Usuário para consultar.")
    @app_commands.guild_only()
    async def balance(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None) -> None:
        if not await self.ensure_enabled(interaction):
            return

        target = usuario or interaction.user
        profile = self.bot.db.get_user(interaction.guild_id, target.id)
        wallet = profile["wallet"]
        bank = profile["bank"]
        total = wallet + bank

        embed = discord.Embed(
            title=f"Saldo de {target.display_name}",
            description=f"Carteira, banco e patrimonio total em **{CURRENCY_NAME}**.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Carteira", value=money(wallet), inline=True)
        embed.add_field(name="Banco", value=money(bank), inline=True)
        embed.add_field(name="Total", value=money(total), inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Master SYNC")
        await respond(interaction, embed, icon_name="coins", author_name="MasterCoins")

    @app_commands.command(name="diario", description="Receba sua recompensa diária de MasterCoins.")
    @app_commands.guild_only()
    async def daily(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_enabled(interaction):
            return

        profile = self.bot.db.get_user(interaction.guild_id, interaction.user.id)
        remaining = cooldown_left(profile["last_daily"], DAILY_COOLDOWN_SECONDS)
        if remaining:
            await respond(interaction, error("Diario em cooldown", f"Volte em **{human_delta(remaining)}** para coletar novamente."), ephemeral=True)
            return

        reward = random.randint(DAILY_REWARD_MIN, DAILY_REWARD_MAX)
        self.bot.db.add_wallet(interaction.guild_id, interaction.user.id, reward)
        self.bot.db.set_cooldown(interaction.guild_id, interaction.user.id, "last_daily", utc_now_iso())

        await respond(interaction, success("Diario coletado", f"Voce recebeu **{money(reward)}** na sua carteira."), icon_name="daily", thumbnail=True)

    @app_commands.command(name="trabalhar", description="Trabalhe e ganhe MasterCoins.")
    @app_commands.guild_only()
    async def work(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_enabled(interaction):
            return

        profile = self.bot.db.get_user(interaction.guild_id, interaction.user.id)
        remaining = cooldown_left(profile["last_work"], WORK_COOLDOWN_SECONDS)
        if remaining:
            await respond(interaction, error("Trabalho em cooldown", f"Voce podera trabalhar novamente em **{human_delta(remaining)}**."), ephemeral=True)
            return

        reward = random.randint(WORK_REWARD_MIN, WORK_REWARD_MAX)
        boost_until = parse_iso(profile["work_boost_until"])
        if boost_until and boost_until > datetime.now(timezone.utc):
            reward *= 2
        jobs = [
            "sincronizou servidores premium",
            "calibrou o cassino do Master SYNC",
            "minerou dados raros da economia",
            "organizou eventos para a comunidade",
            "fez manutenção nos sistemas do bot",
        ]
        self.bot.db.add_wallet(interaction.guild_id, interaction.user.id, reward)
        self.bot.db.set_cooldown(interaction.guild_id, interaction.user.id, "last_work", utc_now_iso())

        await respond(interaction, success("Trabalho concluido", f"Voce {random.choice(jobs)} e ganhou **{money(reward)}**."), icon_name="work", thumbnail=True)

    @app_commands.command(name="pagar", description="Transfira MasterCoins para outro usuário.")
    @app_commands.describe(usuario="Usuário que receberá o pagamento.", valor="Valor em MasterCoins.")
    @app_commands.guild_only()
    async def pay(self, interaction: discord.Interaction, usuario: discord.Member, valor: app_commands.Range[int, 1, 2_000_000_000]) -> None:
        if not await self.ensure_enabled(interaction):
            return
        if usuario.bot:
            await respond(interaction, error("Pagamento bloqueado", "Voce nao pode pagar bots."), ephemeral=True)
            return
        if usuario.id == interaction.user.id:
            await respond(interaction, error("Pagamento bloqueado", "Voce nao pode pagar para si mesmo."), ephemeral=True)
            return

        transferred = self.bot.db.transfer_wallet(interaction.guild_id, interaction.user.id, usuario.id, int(valor))
        if not transferred:
            await respond(interaction, error("Saldo insuficiente", "Voce nao tem esse valor na carteira."), ephemeral=True)
            return

        await respond(interaction, success("Pagamento enviado", f"{interaction.user.mention} enviou **{money(int(valor))}** para {usuario.mention}."), icon_name="coins", thumbnail=True)

    @app_commands.command(name="depositar", description="Deposite MasterCoins da carteira no banco.")
    @app_commands.describe(valor="Valor em MasterCoins.")
    @app_commands.guild_only()
    async def deposit(self, interaction: discord.Interaction, valor: app_commands.Range[int, 1, 2_000_000_000]) -> None:
        if not await self.ensure_enabled(interaction):
            return

        deposited = self.bot.db.deposit(interaction.guild_id, interaction.user.id, int(valor))
        if not deposited:
            await respond(interaction, error("Saldo insuficiente", "Voce nao tem esse valor na carteira."), ephemeral=True)
            return

        await respond(interaction, success("Deposito realizado", f"Voce depositou **{money(int(valor))}** no banco."), ephemeral=True, icon_name="bank", thumbnail=True)

    @app_commands.command(name="sacar", description="Saque MasterCoins do banco para a carteira.")
    @app_commands.describe(valor="Valor em MasterCoins.")
    @app_commands.guild_only()
    async def withdraw(self, interaction: discord.Interaction, valor: app_commands.Range[int, 1, 2_000_000_000]) -> None:
        if not await self.ensure_enabled(interaction):
            return

        withdrawn = self.bot.db.withdraw(interaction.guild_id, interaction.user.id, int(valor))
        if not withdrawn:
            await respond(interaction, error("Banco insuficiente", "Voce nao tem esse valor guardado no banco."), ephemeral=True)
            return

        await respond(interaction, success("Saque realizado", f"Voce sacou **{money(int(valor))}** para a carteira."), ephemeral=True, icon_name="bank", thumbnail=True)

    @app_commands.command(name="ranking", description="Mostra os 10 usuários mais ricos do servidor.")
    @app_commands.guild_only()
    async def ranking(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_enabled(interaction):
            return

        rows = self.bot.db.get_top_users(interaction.guild_id, 10)
        lines: list[str] = []
        for index, row in enumerate(rows, start=1):
            marker = f"`#{index}`"
            member = interaction.guild.get_member(row["user_id"])
            name = member.mention if member else f"<@{row['user_id']}>"
            lines.append(f"{marker} {name} - **{money(row['total'])}**")

        description = "\n".join(lines) if lines else "Ainda nao ha perfis de economia neste servidor."
        message = discord.Embed(
            title="Ranking MasterCoins",
            description=description,
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        message.set_footer(text="Master SYNC")
        await respond(interaction, message, icon_name="ranking", thumbnail=True)

    @app_commands.command(name="perfil", description="Mostra seu perfil de economia e cassino.")
    @app_commands.describe(usuario="Usuário para consultar.")
    @app_commands.guild_only()
    async def profile(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None) -> None:
        if not await self.ensure_enabled(interaction):
            return

        target = usuario or interaction.user
        profile = self.bot.db.get_user(interaction.guild_id, target.id)
        casino = self.bot.db.get_casino_stats(interaction.guild_id, target.id)
        created = unix_timestamp(profile["created_at"])
        created_text = f"<t:{created}:R>" if created else "desconhecido"

        message = discord.Embed(
            title=f"Perfil de {target.display_name}",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        message.set_thumbnail(url=target.display_avatar.url)
        message.add_field(name="Carteira", value=money(profile["wallet"]), inline=True)
        message.add_field(name="Banco", value=money(profile["bank"]), inline=True)
        message.add_field(name="Patrimonio", value=money(profile["wallet"] + profile["bank"]), inline=True)
        message.add_field(name="Total ganho", value=money(profile["total_earned"]), inline=True)
        message.add_field(name="Total perdido", value=money(profile["total_lost"]), inline=True)
        message.add_field(name="Jogos", value=str(casino["games"] or 0), inline=True)
        message.add_field(name="Vitorias", value=str(casino["wins"] or 0), inline=True)
        message.add_field(name="Derrotas", value=str(casino["losses"] or 0), inline=True)
        message.add_field(name="Lucro cassino", value=money(casino["net_profit"] or 0), inline=True)
        message.add_field(name="Perfil criado", value=created_text, inline=False)
        message.set_footer(text="Master SYNC")
        await respond(interaction, message, icon_name="coins", author_name="MasterCoins")

    @app_commands.command(name="loja", description="Mostra itens disponiveis para compra.")
    @app_commands.guild_only()
    async def shop(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_enabled(interaction):
            return
        rows = self.bot.db.get_shop_items(interaction.guild_id)
        lines = [f"`{row['key']}` - **{row['name']}** - {money(row['price'])}\n{row['description']}" for row in rows]
        await respond(interaction, success("Loja MasterCoins", "\n\n".join(lines) if lines else "Nenhum item disponivel."), icon_name="bank", thumbnail=True)

    @app_commands.command(name="comprar", description="Compra um item da loja.")
    @app_commands.describe(item="Codigo do item exibido em /loja.")
    @app_commands.guild_only()
    async def buy(self, interaction: discord.Interaction, item: str) -> None:
        if not await self.ensure_enabled(interaction):
            return
        ok, message = self.bot.db.buy_item(interaction.guild_id, interaction.user.id, item.strip().lower())
        if not ok:
            await respond(interaction, error("Compra recusada", message), ephemeral=True)
            return
        await respond(interaction, success("Compra realizada", f"Item adquirido: **{message}**."), icon_name="bank", thumbnail=True)

    @app_commands.command(name="inventario", description="Mostra seus itens.")
    @app_commands.guild_only()
    async def inventory(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_enabled(interaction):
            return
        rows = self.bot.db.get_inventory(interaction.guild_id, interaction.user.id)
        lines = [f"`{row['item_key']}` - **{row['name'] or row['item_key']}** x{row['quantity']}" for row in rows]
        await respond(interaction, success("Inventario", "\n".join(lines) if lines else "Seu inventario esta vazio."), ephemeral=True, icon_name="user", thumbnail=True)

    @app_commands.command(name="usar", description="Usa um item do inventario.")
    @app_commands.describe(item="Codigo do item no inventario.")
    @app_commands.guild_only()
    async def use_item(self, interaction: discord.Interaction, item: str) -> None:
        if not await self.ensure_enabled(interaction):
            return
        key = item.strip().lower()
        if not self.bot.db.consume_inventory_item(interaction.guild_id, interaction.user.id, key):
            await respond(interaction, error("Item indisponivel", "Voce nao possui esse item no inventario."), ephemeral=True)
            return
        now = datetime.now(timezone.utc)
        if key == "work_booster":
            self.bot.db.set_cooldown(interaction.guild_id, interaction.user.id, "work_boost_until", (now + timedelta(hours=24)).isoformat())
            text = "Booster de trabalho ativado por 24 horas."
        elif key == "mystery_box":
            reward = random.randint(400, 2500)
            self.bot.db.add_wallet(interaction.guild_id, interaction.user.id, reward)
            text = f"A caixa misteriosa liberou **{money(reward)}**."
        elif key == "robbery_protection":
            self.bot.db.set_cooldown(interaction.guild_id, interaction.user.id, "robbery_protection_until", (now + timedelta(days=7)).isoformat())
            text = "Protecao simbolica ativada por 7 dias."
        elif key == "casino_multiplier":
            self.bot.db.set_cooldown(interaction.guild_id, interaction.user.id, "casino_multiplier_until", (now + timedelta(hours=12)).isoformat())
            text = "Multiplicador de cassino ativado por 12 horas. Vitorias recebem 25% a mais de lucro."
        else:
            text = "Item usado com sucesso."
        await respond(interaction, success("Item usado", text), ephemeral=True, icon_name="success", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
