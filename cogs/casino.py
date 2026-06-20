from __future__ import annotations

import asyncio
import random
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, money, respond, success, warning
import config
from config import EMBED_COLOR, ERROR_COLOR, MAX_BET, MIN_BET, SUCCESS_COLOR, WARNING_COLOR
from utils.embed_factory import decorate_embed_with_icon, files_kwargs


SLOT_SYMBOLS = ["Cherry", "Lemon", "Grape", "Bell", "Diamond", "Seven"]
SLOT_WEIGHTS = [26, 24, 20, 15, 9, 6]
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
SUITS = ["S", "H", "D", "C"]
RANKS = [
    ("A", 11),
    ("2", 2),
    ("3", 3),
    ("4", 4),
    ("5", 5),
    ("6", 6),
    ("7", 7),
    ("8", 8),
    ("9", 9),
    ("10", 10),
    ("J", 10),
    ("Q", 10),
    ("K", 10),
]
Card = tuple[str, int]


def cooldown_key(interaction: discord.Interaction) -> tuple[int | None, int]:
    return (interaction.guild_id, interaction.user.id)


def create_deck() -> list[Card]:
    deck = [(f"{rank}{suit}", value) for suit in SUITS for rank, value in RANKS]
    random.shuffle(deck)
    return deck


def hand_value(hand: list[Card]) -> int:
    value = sum(card[1] for card in hand)
    aces = sum(1 for card in hand if card[0].startswith("A"))
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


def is_blackjack(hand: list[Card]) -> bool:
    return len(hand) == 2 and hand_value(hand) == 21


def format_hand(hand: list[Card], *, hide_first: bool = False) -> str:
    if hide_first and hand:
        return "[hidden] " + " ".join(card[0] for card in hand[1:])
    return " ".join(card[0] for card in hand)


class BlackjackView(discord.ui.View):
    def __init__(self, cog: "Casino", interaction: discord.Interaction, bet: int, deck: list[Card], player: list[Card], dealer: list[Card]):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = interaction.guild_id
        self.user_id = interaction.user.id
        self.bet = bet
        self.deck = deck
        self.player = player
        self.dealer = dealer
        self.message: discord.Message | None = None
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await respond(interaction, error("Partida privada", "Somente quem iniciou este Blackjack pode usar esses botoes."), ephemeral=True)
        return False

    def build_embed(self, *, reveal_dealer: bool = False, status: str = "Escolha sua próxima jogada.") -> discord.Embed:
        player_total = hand_value(self.player)
        dealer_total = hand_value(self.dealer)
        message = discord.Embed(
            title="Blackjack Master SYNC",
            description=status,
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        message.add_field(name="Sua mão", value=f"{format_hand(self.player)}\nValor: **{player_total}**", inline=False)
        dealer_value = dealer_total if reveal_dealer else "?"
        message.add_field(
            name="Dealer",
            value=f"{format_hand(self.dealer, hide_first=not reveal_dealer)}\nValor: **{dealer_value}**",
            inline=False,
        )
        message.add_field(name="Aposta", value=money(self.bet), inline=True)
        decorate_embed_with_icon(message, "casino", thumbnail=True)
        return message

    def disable_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    async def finish(self, interaction: discord.Interaction, result: str, payout: int, status: str) -> None:
        if self.finished:
            return
        self.finished = True
        self.disable_buttons()
        payout = self.cog.apply_casino_multiplier(self.guild_id, self.user_id, self.bet, payout)
        profit = self.cog.bot.db.settle_reserved_casino_bet(
            self.guild_id,
            self.user_id,
            "blackjack",
            self.bet,
            result,
            payout,
        )
        self.cog.active_blackjack.discard((self.guild_id, self.user_id))

        final_status = f"{status}\nResultado financeiro: **{money(profit)}**."
        embed = self.build_embed(reveal_dealer=True, status=final_status)
        embed.color = SUCCESS_COLOR if profit > 0 else WARNING_COLOR if profit == 0 else ERROR_COLOR
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.disable_buttons()
        self.cog.active_blackjack.discard((self.guild_id, self.user_id))
        self.cog.bot.db.settle_reserved_casino_bet(
            self.guild_id,
            self.user_id,
            "blackjack",
            self.bet,
            "timeout",
            self.bet,
        )
        if self.message:
            embed = self.build_embed(
                reveal_dealer=True,
                status="Partida expirada por inatividade. A aposta foi devolvida.",
            )
            embed.color = WARNING_COLOR
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                return

    @discord.ui.button(label="Comprar", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.player.append(self.deck.pop())
        value = hand_value(self.player)
        if value > 21:
            await self.finish(interaction, "derrota", 0, "Voce passou de 21. O dealer venceu.")
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Parar", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        while hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())

        player_total = hand_value(self.player)
        dealer_total = hand_value(self.dealer)
        if dealer_total > 21 or player_total > dealer_total:
            await self.finish(interaction, "vitoria", self.bet * 2, "Voce venceu o dealer.")
        elif player_total == dealer_total:
            await self.finish(interaction, "empate", self.bet, "Empate. Sua aposta foi devolvida.")
        else:
            await self.finish(interaction, "derrota", 0, "O dealer venceu esta rodada.")


class Casino(commands.Cog):
    casino = app_commands.Group(name="casino", description="Perfil, ranking e limites do cassino.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_blackjack: set[tuple[int | None, int]] = set()

    def apply_casino_multiplier(self, guild_id: int, user_id: int, bet: int, payout: int) -> int:
        if payout <= bet:
            return payout
        profile = self.bot.db.get_user(guild_id, user_id)
        active_until = self.bot.db._parse_datetime(profile["casino_multiplier_until"])
        if active_until and active_until > discord.utils.utcnow():
            payout += max(1, (payout - bet) // 4)
        settings = self.bot.db.get_guild_settings(guild_id)
        edge = min(max(float(settings["casino_house_edge_percent"] or 0), 0), 90)
        if edge:
            payout = bet + int((payout - bet) * ((100 - edge) / 100))
        return max(0, payout)

    async def ensure_ready(self, interaction: discord.Interaction, bet: int) -> bool:
        settings = self.bot.db.get_guild_settings(interaction.guild_id)
        if not config.is_global_admin(interaction.user.id) and not self.bot.db.feature_enabled(interaction.guild_id, "casino"):
            await respond(interaction, error("Cassino indisponivel", config.SUBSCRIPTION_BLOCK_MESSAGE), ephemeral=True)
            return False
        if not settings["economy_enabled"]:
            await respond(interaction, error("Economia desativada", "A economia precisa estar ativa para usar o cassino."), ephemeral=True)
            return False
        if not settings["casino_enabled"]:
            await respond(interaction, error("Cassino desativado", "O cassino esta desativado neste servidor."), ephemeral=True)
            return False
        min_bet = int(settings["casino_min_bet"] or MIN_BET)
        max_bet = int(settings["casino_max_bet"] or MAX_BET)
        if bet < min_bet:
            await respond(interaction, error("Aposta muito baixa", f"A aposta minima e **{money(min_bet)}**."), ephemeral=True)
            return False
        if bet > max_bet:
            await respond(interaction, error("Aposta muito alta", f"A aposta maxima e **{money(max_bet)}**."), ephemeral=True)
            return False
        profile = self.bot.db.get_user(interaction.guild_id, interaction.user.id)
        if profile["wallet"] < bet:
            await respond(interaction, error("Saldo insuficiente", "Voce precisa ter a aposta disponivel na carteira."), ephemeral=True)
            return False
        loss_limit = int(settings["casino_daily_loss_limit"] or 0)
        if loss_limit > 0:
            row = self.bot.db.fetchone(
                """
                SELECT COALESCE(SUM(CASE WHEN profit < 0 THEN -profit ELSE 0 END), 0) AS lost
                FROM casino_history
                WHERE guild_id = ? AND user_id = ? AND datetime(created_at) >= datetime('now', 'start of day')
                """,
                (interaction.guild_id, interaction.user.id),
            )
            lost_today = int(row["lost"] or 0) if row else 0
            if lost_today + bet > loss_limit:
                await respond(interaction, error("Limite diario atingido", f"Seu limite diario de perdas e **{money(loss_limit)}**."), ephemeral=True)
                return False
        return True

    @casino.command(name="perfil", description="Mostra seu perfil de cassino.")
    @app_commands.guild_only()
    async def casino_profile(self, interaction: discord.Interaction, usuario: discord.Member | None = None) -> None:
        target = usuario or interaction.user
        stats = self.bot.db.get_casino_stats(interaction.guild_id, target.id)
        message = success("Perfil de cassino", f"Usuario: {target.mention}")
        message.add_field(name="Jogos", value=str(stats["games"] or 0), inline=True)
        message.add_field(name="Vitorias", value=str(stats["wins"] or 0), inline=True)
        message.add_field(name="Derrotas", value=str(stats["losses"] or 0), inline=True)
        message.add_field(name="Lucro liquido", value=money(stats["net_profit"] or 0), inline=True)
        await respond(interaction, message, icon_name="casino", thumbnail=True)

    @casino.command(name="ranking", description="Mostra ranking de lucro no cassino.")
    @app_commands.guild_only()
    async def casino_ranking(self, interaction: discord.Interaction) -> None:
        rows = self.bot.db.fetchall(
            """
            SELECT user_id, COALESCE(SUM(profit), 0) AS net
            FROM casino_history
            WHERE guild_id = ?
            GROUP BY user_id
            ORDER BY net DESC
            LIMIT 10
            """,
            (interaction.guild_id,),
        )
        lines = [f"`#{idx}` <@{row['user_id']}> - {money(row['net'])}" for idx, row in enumerate(rows, 1)]
        await respond(interaction, success("Ranking do cassino", "\n".join(lines) if lines else "Sem historico ainda."), icon_name="casino", thumbnail=True)

    @casino.command(name="historico", description="Mostra suas ultimas apostas.")
    @app_commands.guild_only()
    async def casino_history(self, interaction: discord.Interaction) -> None:
        rows = self.bot.db.fetchall(
            "SELECT * FROM casino_history WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 10",
            (interaction.guild_id, interaction.user.id),
        )
        lines = [f"{row['game']} - aposta {money(row['bet'])} - resultado {row['result']} - lucro {money(row['profit'])}" for row in rows]
        await respond(interaction, success("Historico do cassino", "\n".join(lines) if lines else "Nenhuma aposta registrada."), ephemeral=True, icon_name="casino", thumbnail=True)

    @casino.command(name="limites", description="Mostra limites de aposta deste servidor.")
    @app_commands.guild_only()
    async def casino_limits(self, interaction: discord.Interaction) -> None:
        settings = self.bot.db.get_guild_settings(interaction.guild_id)
        loss_limit = int(settings["casino_daily_loss_limit"] or 0)
        loss_text = money(loss_limit) if loss_limit else "desativado"
        description = (
            f"Aposta minima: **{money(settings['casino_min_bet'])}**\n"
            f"Aposta maxima: **{money(settings['casino_max_bet'])}**\n"
            f"Limite diario de perda: **{loss_text}**\n"
            f"Taxa da casa: **{float(settings['casino_house_edge_percent'] or 0):.1f}%**"
        )
        await respond(interaction, success("Limites do cassino", description), ephemeral=True, icon_name="casino", thumbnail=True)

    def result_embed(self, title: str, result: str, bet: int, payout: int, profit: int, *, color: int, icon_name: str = "casino") -> discord.Embed:
        message = discord.Embed(
            title=title,
            description=result,
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        message.add_field(name="Aposta", value=money(bet), inline=True)
        message.add_field(name="Pagamento", value=money(payout), inline=True)
        message.add_field(name="Lucro/Perda", value=money(profit), inline=True)
        decorate_embed_with_icon(message, icon_name, thumbnail=True)
        return message

    def settle(self, interaction: discord.Interaction, game: str, bet: int, result: str, payout: int) -> int | None:
        return self.bot.db.settle_instant_casino(interaction.guild_id, interaction.user.id, game, bet, result, payout)

    @app_commands.command(name="cassino", description="Mostra os jogos e limites do cassino Master SYNC.")
    @app_commands.guild_only()
    async def casino_menu(self, interaction: discord.Interaction) -> None:
        settings = self.bot.db.get_guild_settings(interaction.guild_id)
        if not settings["economy_enabled"]:
            await respond(interaction, error("Economia desativada", "A economia precisa estar ativa para usar o cassino."), ephemeral=True)
            return
        if not settings["casino_enabled"]:
            await respond(interaction, error("Cassino desativado", "O cassino esta desativado neste servidor."), ephemeral=True)
            return

        message = discord.Embed(
            title="Cassino Master SYNC",
            description="Escolha um jogo, defina sua aposta e boa sorte.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        message.add_field(name="Limites", value=f"Mínima: **{money(MIN_BET)}**\nMáxima: **{money(MAX_BET)}**", inline=True)
        message.add_field(name="Jogos", value="`/slot`, `/coinflip`, `/roleta`, `/blackjack`, `/dados`", inline=False)
        message.add_field(name="Dica", value="Use `/saldo` para conferir sua carteira antes de apostar.", inline=False)
        message.set_footer(text="Master SYNC")
        await respond(interaction, message, icon_name="casino", thumbnail=True, author_name="Cassino")

    @app_commands.command(name="slot", description="Gire a slot machine do Master SYNC.")
    @app_commands.describe(aposta="Valor da aposta em MasterCoins.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5.0, key=cooldown_key)
    async def slot(self, interaction: discord.Interaction, aposta: app_commands.Range[int, 1, 2_000_000_000]) -> None:
        bet = int(aposta)
        if not await self.ensure_ready(interaction, bet):
            return

        symbols = random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)
        counts = {symbol: symbols.count(symbol) for symbol in set(symbols)}
        if symbols == ["Seven", "Seven", "Seven"]:
            multiplier = 15
        elif symbols == ["Diamond", "Diamond", "Diamond"]:
            multiplier = 10
        elif len(counts) == 1:
            multiplier = 5
        elif 2 in counts.values():
            multiplier = 2
        else:
            multiplier = 0

        payout = bet * multiplier if multiplier else 0
        result = "vitoria" if payout else "derrota"
        payout = self.apply_casino_multiplier(interaction.guild_id, interaction.user.id, bet, payout)
        profit = self.settle(interaction, "slot", bet, result, payout)
        if profit is None:
            await respond(interaction, error("Saldo insuficiente", "Seu saldo mudou antes da aposta ser processada."), ephemeral=True)
            return

        await interaction.response.defer()
        frames = [
            ["...", "...", "..."],
            [symbols[0], "...", "..."],
            [symbols[0], symbols[1], "..."],
            symbols,
        ]
        spinning = discord.Embed(
            title="Slot Machine",
            description="Girando...\n\n`... | ... | ...`",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        files = decorate_embed_with_icon(spinning, "slot", thumbnail=True)
        message = await interaction.followup.send(embed=spinning, wait=True, **files_kwargs(files))
        for frame in frames:
            await asyncio.sleep(0.45)
            frame_embed = discord.Embed(
                title="Slot Machine",
                description=f"Girando...\n\n`{' | '.join(frame)}`",
                color=EMBED_COLOR,
                timestamp=discord.utils.utcnow(),
            )
            decorate_embed_with_icon(frame_embed, "slot", thumbnail=True)
            await message.edit(
                embed=frame_embed
            )

        color = SUCCESS_COLOR if profit > 0 else ERROR_COLOR
        description = f"Resultado: `{' | '.join(symbols)}`"
        if multiplier:
            description += f"\nMultiplicador: **{multiplier}x**"
        else:
            description += "\nNão foi desta vez."
        await message.edit(embed=self.result_embed("Slot Machine", description, bet, payout, profit, color=color, icon_name="slot"))

    @app_commands.command(name="coinflip", description="Aposte em cara ou coroa.")
    @app_commands.describe(escolha="Escolha cara ou coroa.", aposta="Valor da aposta em MasterCoins.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 4.0, key=cooldown_key)
    async def coinflip(self, interaction: discord.Interaction, escolha: Literal["cara", "coroa"], aposta: app_commands.Range[int, 1, 2_000_000_000]) -> None:
        bet = int(aposta)
        if not await self.ensure_ready(interaction, bet):
            return

        result_side = random.choice(["cara", "coroa"])
        won = escolha == result_side
        payout = bet * 2 if won else 0
        payout = self.apply_casino_multiplier(interaction.guild_id, interaction.user.id, bet, payout)
        profit = self.settle(interaction, "coinflip", bet, "vitoria" if won else "derrota", payout)
        if profit is None:
            await respond(interaction, error("Saldo insuficiente", "Seu saldo mudou antes da aposta ser processada."), ephemeral=True)
            return

        description = f"Caiu **{result_side}**.\nVoce escolheu **{escolha}**."
        await respond(
            interaction,
            self.result_embed(
                "Cara ou Coroa",
                description,
                bet,
                payout,
                profit,
                color=SUCCESS_COLOR if won else ERROR_COLOR,
                icon_name="casino",
            ),
            icon_name="casino",
            thumbnail=True,
        )

    @app_commands.command(name="roleta", description="Aposte em vermelho, preto ou verde.")
    @app_commands.describe(cor="Cor escolhida.", aposta="Valor da aposta em MasterCoins.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5.0, key=cooldown_key)
    async def roulette(self, interaction: discord.Interaction, cor: Literal["vermelho", "preto", "verde"], aposta: app_commands.Range[int, 1, 2_000_000_000]) -> None:
        bet = int(aposta)
        if not await self.ensure_ready(interaction, bet):
            return

        number = random.randint(0, 36)
        if number == 0:
            result_color = "verde"
        elif number in RED_NUMBERS:
            result_color = "vermelho"
        else:
            result_color = "preto"

        multiplier = 14 if cor == "verde" else 2
        won = cor == result_color
        payout = bet * multiplier if won else 0
        payout = self.apply_casino_multiplier(interaction.guild_id, interaction.user.id, bet, payout)
        profit = self.settle(interaction, "roleta", bet, "vitoria" if won else "derrota", payout)
        if profit is None:
            await respond(interaction, error("Saldo insuficiente", "Seu saldo mudou antes da aposta ser processada."), ephemeral=True)
            return

        description = f"A bolinha caiu no numero **{number}**, cor **{result_color}**.\nSua aposta: **{cor}**."
        await respond(
            interaction,
            self.result_embed(
                "Roleta",
                description,
                bet,
                payout,
                profit,
                color=SUCCESS_COLOR if won else ERROR_COLOR,
                icon_name="casino",
            ),
            icon_name="casino",
            thumbnail=True,
        )

    @app_commands.command(name="blackjack", description="Jogue Blackjack contra o dealer.")
    @app_commands.describe(aposta="Valor da aposta em MasterCoins.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 8.0, key=cooldown_key)
    async def blackjack(self, interaction: discord.Interaction, aposta: app_commands.Range[int, 1, 2_000_000_000]) -> None:
        bet = int(aposta)
        if not await self.ensure_ready(interaction, bet):
            return

        key = (interaction.guild_id, interaction.user.id)
        if key in self.active_blackjack:
            await respond(interaction, warning("Partida em andamento", "Finalize seu Blackjack atual antes de iniciar outro."), ephemeral=True, icon_name="casino", thumbnail=True)
            return

        reserved = self.bot.db.reserve_casino_bet(interaction.guild_id, interaction.user.id, bet)
        if not reserved:
            await respond(interaction, error("Saldo insuficiente", "Nao foi possivel reservar a aposta."), ephemeral=True)
            return

        self.active_blackjack.add(key)
        try:
            deck = create_deck()
            player = [deck.pop(), deck.pop()]
            dealer = [deck.pop(), deck.pop()]

            player_blackjack = is_blackjack(player)
            dealer_blackjack = is_blackjack(dealer)
            if player_blackjack or dealer_blackjack:
                if player_blackjack and dealer_blackjack:
                    payout = bet
                    result = "empate"
                    status = "Dois blackjacks. A aposta foi devolvida."
                elif player_blackjack:
                    payout = (bet * 5) // 2
                    result = "vitoria"
                    status = "Blackjack natural. Pagamento de 2.5x."
                else:
                    payout = 0
                    result = "derrota"
                    status = "O dealer fez Blackjack natural."

                payout = self.apply_casino_multiplier(interaction.guild_id, interaction.user.id, bet, payout)
                profit = self.bot.db.settle_reserved_casino_bet(interaction.guild_id, interaction.user.id, "blackjack", bet, result, payout)
                self.active_blackjack.discard(key)
                embed = discord.Embed(
                    title="Blackjack Master SYNC",
                    description=f"{status}\nResultado financeiro: **{money(profit)}**.",
                    color=SUCCESS_COLOR if profit > 0 else WARNING_COLOR if profit == 0 else ERROR_COLOR,
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(name="Sua mão", value=f"{format_hand(player)}\nValor: **{hand_value(player)}**", inline=False)
                embed.add_field(name="Dealer", value=f"{format_hand(dealer)}\nValor: **{hand_value(dealer)}**", inline=False)
                embed.add_field(name="Aposta", value=money(bet), inline=True)
                await respond(interaction, embed, icon_name="casino", thumbnail=True)
                return

            view = BlackjackView(self, interaction, bet, deck, player, dealer)
            embed = view.build_embed()
            files = decorate_embed_with_icon(embed, "casino", thumbnail=True)
            await interaction.response.send_message(embed=embed, view=view, **files_kwargs(files))
            view.message = await interaction.original_response()
        except Exception:
            self.active_blackjack.discard(key)
            self.bot.db.settle_reserved_casino_bet(interaction.guild_id, interaction.user.id, "blackjack", bet, "cancelado", bet)
            raise

    @app_commands.command(name="dados", description="Aposte em um número de 1 a 6.")
    @app_commands.describe(aposta="Valor da aposta em MasterCoins.", numero="Número escolhido de 1 a 6.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 4.0, key=cooldown_key)
    async def dice(self, interaction: discord.Interaction, aposta: app_commands.Range[int, 1, 2_000_000_000], numero: app_commands.Range[int, 1, 6]) -> None:
        bet = int(aposta)
        chosen = int(numero)
        if not await self.ensure_ready(interaction, bet):
            return

        rolled = random.randint(1, 6)
        won = chosen == rolled
        payout = bet * 5 if won else 0
        payout = self.apply_casino_multiplier(interaction.guild_id, interaction.user.id, bet, payout)
        profit = self.settle(interaction, "dados", bet, "vitoria" if won else "derrota", payout)
        if profit is None:
            await respond(interaction, error("Saldo insuficiente", "Seu saldo mudou antes da aposta ser processada."), ephemeral=True)
            return

        description = f"O dado caiu em **{rolled}**.\nVoce escolheu **{chosen}**."
        await respond(
            interaction,
            self.result_embed(
                "Dados",
                description,
                bet,
                payout,
                profit,
                color=SUCCESS_COLOR if won else ERROR_COLOR,
                icon_name="dice",
            ),
            icon_name="dice",
            thumbnail=True,
        )

    @app_commands.command(name="raspadinha", description="Jogue uma raspadinha simples.")
    @app_commands.describe(aposta="Valor da aposta em MasterCoins.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5.0, key=cooldown_key)
    async def scratch(self, interaction: discord.Interaction, aposta: app_commands.Range[int, 1, 2_000_000_000]) -> None:
        bet = int(aposta)
        if not await self.ensure_ready(interaction, bet):
            return
        cards = random.choices(["Bronze", "Prata", "Ouro", "Master"], weights=[45, 30, 18, 7], k=3)
        counts = {card: cards.count(card) for card in set(cards)}
        multiplier = 0
        if counts.get("Master") == 3:
            multiplier = 12
        elif max(counts.values()) == 3:
            multiplier = 4
        elif max(counts.values()) == 2:
            multiplier = 2
        payout = bet * multiplier if multiplier else 0
        payout = self.apply_casino_multiplier(interaction.guild_id, interaction.user.id, bet, payout)
        profit = self.settle(interaction, "raspadinha", bet, "vitoria" if payout else "derrota", payout)
        if profit is None:
            await respond(interaction, error("Saldo insuficiente", "Seu saldo mudou antes da aposta ser processada."), ephemeral=True)
            return
        description = f"Cartas: `{' | '.join(cards)}`\nMultiplicador: **{multiplier}x**" if multiplier else f"Cartas: `{' | '.join(cards)}`\nSem premio nesta rodada."
        await respond(interaction, self.result_embed("Raspadinha", description, bet, payout, profit, color=SUCCESS_COLOR if profit > 0 else ERROR_COLOR, icon_name="casino"), icon_name="casino", thumbnail=True)

    @app_commands.command(name="tesouro", description="Caca ao tesouro simples.")
    @app_commands.describe(aposta="Valor da aposta em MasterCoins.", escolha="Escolha uma caixa de 1 a 5.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 6.0, key=cooldown_key)
    async def treasure(self, interaction: discord.Interaction, aposta: app_commands.Range[int, 1, 2_000_000_000], escolha: app_commands.Range[int, 1, 5]) -> None:
        bet = int(aposta)
        if not await self.ensure_ready(interaction, bet):
            return
        winning = random.randint(1, 5)
        won = int(escolha) == winning
        payout = bet * 4 if won else 0
        payout = self.apply_casino_multiplier(interaction.guild_id, interaction.user.id, bet, payout)
        profit = self.settle(interaction, "tesouro", bet, "vitoria" if won else "derrota", payout)
        if profit is None:
            await respond(interaction, error("Saldo insuficiente", "Seu saldo mudou antes da aposta ser processada."), ephemeral=True)
            return
        description = f"Voce escolheu a caixa **{escolha}**.\nO tesouro estava na caixa **{winning}**."
        await respond(interaction, self.result_embed("Caca ao tesouro", description, bet, payout, profit, color=SUCCESS_COLOR if won else ERROR_COLOR, icon_name="casino"), icon_name="casino", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Casino(bot))
