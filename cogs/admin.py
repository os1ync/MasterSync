from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, respond, success
from database.db import utc_now_iso
from utils.checks import premium_required
from utils.embed_factory import decorate_embed_with_icon, files_kwargs


class ConfigPanel(discord.ui.View):
    def __init__(self, bot: commands.Bot, author_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.author_id = author_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        allowed = interaction.user.id == self.author_id and isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator
        if not allowed:
            await respond(interaction, error("Painel restrito", "Apenas o administrador que abriu o painel pode usar esta interface."), ephemeral=True)
        return allowed

    async def toggle(self, interaction: discord.Interaction, column: str, label: str) -> None:
        settings = self.bot.db.get_guild_settings(self.guild_id)
        value = 0 if settings[column] else 1
        self.bot.db.update_guild_setting(self.guild_id, column, value)
        state = "ativado" if value else "desativado"
        await respond(interaction, success("Configuracao atualizada", f"{label} foi {state}."), ephemeral=True, icon_name="config", thumbnail=True)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Selecionar canal de boas-vindas",
        channel_types=[discord.ChannelType.text],
        row=0,
    )
    async def welcome_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect) -> None:
        channel = select.values[0]
        self.bot.db.update_guild_setting(self.guild_id, "welcome_channel_id", channel.id)
        await respond(interaction, success("Canal atualizado", f"Boas-vindas serao enviadas em {channel.mention}."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Selecionar canal de logs",
        channel_types=[discord.ChannelType.text],
        row=1,
    )
    async def logs_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect) -> None:
        channel = select.values[0]
        self.bot.db.update_guild_setting(self.guild_id, "logs_channel_id", channel.id)
        await respond(interaction, success("Canal atualizado", f"Logs serao enviados em {channel.mention}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Selecionar cargo automatico",
        row=2,
    )
    async def autorole_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect) -> None:
        role = select.values[0]
        self.bot.db.execute(
            "INSERT OR IGNORE INTO autoroles (guild_id, role_id, mode, label, created_at) VALUES (?, ?, 'join', ?, ?)",
            (self.guild_id, role.id, role.name, utc_now_iso()),
        )
        self.bot.db.update_guild_setting(self.guild_id, "autorole_enabled", 1)
        await respond(interaction, success("Cargo automatico salvo", f"O cargo {role.mention} sera usado no autorole."), ephemeral=True, icon_name="user", thumbnail=True)

    @discord.ui.button(label="Boas-vindas", style=discord.ButtonStyle.secondary, row=3)
    async def toggle_welcome(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.toggle(interaction, "welcome_enabled", "Boas-vindas")

    @discord.ui.button(label="Economia", style=discord.ButtonStyle.secondary, row=3)
    async def toggle_economy(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.toggle(interaction, "economy_enabled", "Economia")

    @discord.ui.button(label="Cassino", style=discord.ButtonStyle.secondary, row=3)
    async def toggle_casino(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.toggle(interaction, "casino_enabled", "Cassino")

    @discord.ui.button(label="Tickets", style=discord.ButtonStyle.secondary, row=3)
    async def toggle_tickets(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.toggle(interaction, "tickets_enabled", "Tickets")

    @discord.ui.button(label="Niveis", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_levels(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.toggle(interaction, "levels_enabled", "Niveis")

    @discord.ui.button(label="Sorteios", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.toggle(interaction, "giveaways_enabled", "Sorteios")

    @discord.ui.button(label="Automod", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_automod(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.toggle(interaction, "automod_enabled", "Automod")

    @discord.ui.button(label="Anti-raid", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_antiraid(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.toggle(interaction, "antiraid_enabled", "Anti-raid")


class Admin(commands.Cog):
    config = app_commands.Group(name="config", description="Configurações gerais do Master SYNC.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="painel", description="Abre o painel premium de configuracao do Master SYNC.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @premium_required
    async def panel(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Painel Master SYNC",
            description=(
                "Use os menus para definir canais e cargo automatico. "
                "Use os botoes para ativar ou desativar sistemas do servidor."
            ),
            color=0x7C3AED,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Acesso", value="Somente administradores podem usar este painel.", inline=False)
        files = decorate_embed_with_icon(embed, "settings", thumbnail=True, author_name="Configuracao")
        await interaction.response.send_message(embed=embed, view=ConfigPanel(self.bot, interaction.user.id, interaction.guild_id), ephemeral=True, **files_kwargs(files))

    @config.command(name="logs", description="Define o canal de logs do servidor.")
    @app_commands.describe(canal="Canal onde os logs serão enviados.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def logs(self, interaction: discord.Interaction, canal: discord.TextChannel) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "logs_channel_id", canal.id)
        await respond(interaction, success("Canal de logs configurado", f"Os logs serão enviados em {canal.mention}."), ephemeral=True, icon_name="shield", thumbnail=True)

    @config.command(name="prefixo", description="Define o prefixo futuro do bot.")
    @app_commands.describe(prefixo="Novo prefixo, entre 1 e 5 caracteres.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def prefix(self, interaction: discord.Interaction, prefixo: str) -> None:
        prefixo = prefixo.strip()
        if not 1 <= len(prefixo) <= 5:
            await respond(interaction, error("Prefixo invalido", "Use um prefixo entre 1 e 5 caracteres."), ephemeral=True)
            return
        self.bot.db.update_guild_setting(interaction.guild_id, "prefix", prefixo)
        await respond(interaction, success("Prefixo salvo", f"Prefixo futuro definido como `{prefixo}`."), ephemeral=True, icon_name="config", thumbnail=True)

    @config.command(name="cassino", description="Ativa ou desativa o cassino.")
    @app_commands.describe(estado="Escolha ativar ou desativar.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def casino(self, interaction: discord.Interaction, estado: Literal["ativar", "desativar"]) -> None:
        enabled = 1 if estado == "ativar" else 0
        self.bot.db.update_guild_setting(interaction.guild_id, "casino_enabled", enabled)
        status = "ativado" if enabled else "desativado"
        await respond(interaction, success("Configuracao atualizada", f"O cassino foi **{status}** neste servidor."), ephemeral=True, icon_name="casino", thumbnail=True)

    @config.command(name="cassino-limites", description="Define limites e taxa da casa do cassino.")
    @app_commands.describe(
        aposta_minima="Aposta minima em MasterCoins.",
        aposta_maxima="Aposta maxima em MasterCoins.",
        perda_diaria="Limite diario opcional de perda. Use 0 para desativar.",
        taxa_casa="Percentual descontado do lucro em apostas vencedoras.",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def casino_limits(
        self,
        interaction: discord.Interaction,
        aposta_minima: app_commands.Range[int, 1, 2_000_000_000],
        aposta_maxima: app_commands.Range[int, 1, 2_000_000_000],
        perda_diaria: app_commands.Range[int, 0, 2_000_000_000] = 0,
        taxa_casa: app_commands.Range[float, 0.0, 50.0] = 0.0,
    ) -> None:
        if int(aposta_minima) > int(aposta_maxima):
            await respond(interaction, error("Limites invalidos", "A aposta minima nao pode ser maior que a aposta maxima."), ephemeral=True)
            return
        self.bot.db.update_guild_setting(interaction.guild_id, "casino_min_bet", int(aposta_minima))
        self.bot.db.update_guild_setting(interaction.guild_id, "casino_max_bet", int(aposta_maxima))
        self.bot.db.update_guild_setting(interaction.guild_id, "casino_daily_loss_limit", int(perda_diaria))
        self.bot.db.update_guild_setting(interaction.guild_id, "casino_house_edge_percent", float(taxa_casa))
        await respond(interaction, success("Limites do cassino salvos", "Apostas, perda diaria e taxa da casa foram atualizadas."), ephemeral=True, icon_name="casino", thumbnail=True)

    @config.command(name="economia", description="Ativa ou desativa a economia.")
    @app_commands.describe(estado="Escolha ativar ou desativar.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def economy(self, interaction: discord.Interaction, estado: Literal["ativar", "desativar"]) -> None:
        enabled = 1 if estado == "ativar" else 0
        self.bot.db.update_guild_setting(interaction.guild_id, "economy_enabled", enabled)
        status = "ativada" if enabled else "desativada"
        await respond(interaction, success("Configuracao atualizada", f"A economia foi **{status}** neste servidor."), ephemeral=True, icon_name="coins", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
