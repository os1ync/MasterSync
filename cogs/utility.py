from __future__ import annotations

import platform
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, human_delta, info, respond, success
from config import BRAND_NAME, EMBED_COLOR
from utils.embed_factory import decorate_embed_with_icon, files_kwargs
from utils.formatters import discord_time, human_bool


HELP_CATEGORIES = {
    "geral": {
        "title": "Ajuda geral",
        "description": "Comandos principais para configurar, operar e consultar o Master SYNC.",
        "fields": [
            ("Configuracao", "`/painel`, `/config logs`, `/config prefixo`, `/logs configurar`"),
            ("Utilidades", "`/ping`, `/avatar`, `/banner`, `/userinfo`, `/serverinfo`, `/botinfo`, `/convite`, `/status`"),
            ("Assinatura", "`/assinatura ativar`, `/assinatura renovar`, `/assinatura status`, `/assinatura listar`"),
        ],
    },
    "comunidade": {
        "title": "Comunidade",
        "description": "Ferramentas para recepcao, crescimento e retencao de membros.",
        "fields": [
            ("Boas-vindas", "`/boasvindas configurar`, `/boasvindas mensagem`, `/boasvindas fundo`, `/boasvindas testar`"),
            ("Niveis", "`/level`, `/rank`, `/levels configurar`, `/levels cargo`, `/levels reset`"),
            ("Autorole", "`/autorole configurar`, `/autorole adicionar`, `/autorole remover`, `/autorole listar`"),
            ("Sorteios", "`/sorteio criar`, `/sorteio reroll`, `/sorteio cancelar`, `/sorteio listar`"),
        ],
    },
    "economia": {
        "title": "Economia e cassino",
        "description": "Sistema MasterCoins, loja, inventario e jogos de cassino.",
        "fields": [
            ("Economia", "`/saldo`, `/diario`, `/trabalhar`, `/pagar`, `/depositar`, `/sacar`, `/ranking`, `/perfil`"),
            ("Loja", "`/loja`, `/comprar`, `/inventario`, `/usar`"),
            ("Cassino", "`/cassino`, `/casino perfil`, `/casino ranking`, `/casino historico`, `/casino limites`"),
            ("Jogos", "`/slot`, `/coinflip`, `/dados`, `/roleta`, `/blackjack`, `/raspadinha`, `/tesouro`"),
        ],
    },
    "suporte": {
        "title": "Suporte e moderacao",
        "description": "Tickets, logs, moderacao avancada, automod e anti-raid.",
        "fields": [
            ("Tickets", "`/ticket painel`, `/ticket configurar`, `/ticket fechar`, `/ticket assumir`, `/ticket transcript`"),
            ("Moderacao", "`/ban`, `/unban`, `/kick`, `/timeout`, `/untimeout`, `/warn`, `/warnings`, `/limpar`, `/slowmode`"),
            ("Automod", "`/automod painel`, `/automod antilink`, `/automod antispam`, `/automod anticaps`, `/automod antimencoes`, `/automod punicao`"),
            ("Anti-raid", "`/antiraid ativar`, `/antiraid configurar`, `/lockdown`, `/unlockdown`"),
        ],
    },
}


def build_help_embed(category: str = "geral") -> discord.Embed:
    data = HELP_CATEGORIES.get(category, HELP_CATEGORIES["geral"])
    embed = discord.Embed(
        title=data["title"],
        description=data["description"],
        color=EMBED_COLOR,
        timestamp=discord.utils.utcnow(),
    )
    for name, value in data["fields"]:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text="Master SYNC")
    return embed


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.select(
        placeholder="Selecionar categoria",
        options=[
            discord.SelectOption(label="Geral", value="geral"),
            discord.SelectOption(label="Comunidade", value="comunidade"),
            discord.SelectOption(label="Economia e cassino", value="economia"),
            discord.SelectOption(label="Suporte e moderacao", value="suporte"),
        ],
    )
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        await interaction.response.edit_message(embed=build_help_embed(select.values[0]), view=self)


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.started_at = datetime.now(timezone.utc)

    @app_commands.command(name="ping", description="Mostra a latencia do bot.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        await respond(interaction, info("Pong", f"Latencia atual: **{latency}ms**."), icon_name="info", thumbnail=True)

    @app_commands.command(name="avatar", description="Mostra o avatar de um usuario.")
    @app_commands.describe(usuario="Usuario para ver o avatar.")
    @app_commands.guild_only()
    async def avatar(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None) -> None:
        target = usuario or interaction.user
        embed = discord.Embed(
            title=f"Avatar de {target.display_name}",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_image(url=target.display_avatar.with_size(1024).url)
        embed.set_footer(text="Master SYNC")
        await respond(interaction, embed, icon_name="user", author_name="Perfil de usuario")

    @app_commands.command(name="banner", description="Mostra o banner de um usuario quando disponivel.")
    @app_commands.describe(usuario="Usuario para consultar.")
    @app_commands.guild_only()
    async def banner(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None) -> None:
        target = usuario or interaction.user
        fetched = await self.bot.fetch_user(target.id)
        if fetched.banner is None:
            await respond(interaction, error("Banner indisponivel", "Este usuario nao possui banner publico."), ephemeral=True)
            return
        embed = discord.Embed(
            title=f"Banner de {target.display_name}",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_image(url=fetched.banner.with_size(1024).url)
        embed.set_footer(text="Master SYNC")
        await respond(interaction, embed, icon_name="user", author_name="Perfil de usuario")

    @app_commands.command(name="userinfo", description="Mostra informacoes sobre um usuario.")
    @app_commands.describe(usuario="Usuario para consultar.")
    @app_commands.guild_only()
    async def userinfo(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None) -> None:
        target = usuario or interaction.user
        roles = [role.mention for role in reversed(target.roles) if role.name != "@everyone"]
        roles_text = ", ".join(roles[:8]) if roles else "Nenhum cargo"
        if len(roles) > 8:
            roles_text += f" e mais {len(roles) - 8}"

        embed = discord.Embed(
            title=f"Informacoes de {target.display_name}",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Bot", value="Sim" if target.bot else "Nao", inline=True)
        embed.add_field(name="Cargo mais alto", value=target.top_role.mention, inline=True)
        embed.add_field(name="Conta criada", value=f"<t:{int(target.created_at.timestamp())}:F>", inline=False)
        joined = f"<t:{int(target.joined_at.timestamp())}:F>" if target.joined_at else "desconhecido"
        embed.add_field(name="Entrou no servidor", value=joined, inline=False)
        embed.add_field(name=f"Cargos ({len(roles)})", value=roles_text, inline=False)
        embed.set_footer(text="Master SYNC")
        await respond(interaction, embed, icon_name="user", author_name="Informacoes do usuario")

    @app_commands.command(name="serverinfo", description="Mostra informacoes do servidor.")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        embed = discord.Embed(
            title=f"{guild.name}",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        owner = guild.owner.mention if guild.owner else f"`{guild.owner_id}`"
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Dono", value=owner, inline=True)
        embed.add_field(name="Membros", value=str(guild.member_count or 0), inline=True)
        embed.add_field(name="Canais", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Cargos", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Boosts", value=str(guild.premium_subscription_count or 0), inline=True)
        embed.add_field(name="Criado em", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=False)
        embed.set_footer(text="Master SYNC")
        await respond(interaction, embed, icon_name="info", author_name="Servidor")

    @app_commands.command(name="botinfo", description="Mostra informacoes do bot.")
    async def botinfo(self, interaction: discord.Interaction) -> None:
        uptime = datetime.now(timezone.utc) - self.started_at
        uptime_text = human_delta(int(uptime.total_seconds()))
        embed = discord.Embed(
            title=f"{BRAND_NAME}",
            description="Bot premium all-in-one para comunidades Discord.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Uptime", value=uptime_text, inline=True)
        embed.add_field(name="Servidores", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="Cogs", value=str(len(self.bot.cogs)), inline=True)
        embed.set_footer(text="Master SYNC")
        await respond(interaction, embed, icon_name="info", author_name="Bot")

    @app_commands.command(name="convite", description="Gera o link de convite do bot.")
    async def invite(self, interaction: discord.Interaction) -> None:
        if not self.bot.user:
            await respond(interaction, error("Convite indisponivel", "O bot ainda nao esta pronto para gerar convite."), ephemeral=True)
            return
        permissions = discord.Permissions(administrator=True)
        invite_url = discord.utils.oauth_url(self.bot.user.id, permissions=permissions, scopes=("bot", "applications.commands"))
        await respond(interaction, info("Convite Master SYNC", f"Use este link para adicionar o bot:\n{invite_url}"), ephemeral=True, icon_name="info", thumbnail=True)

    @app_commands.command(name="status", description="Mostra status operacional e assinatura do servidor.")
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction) -> None:
        subscription = self.bot.db.get_subscription(interaction.guild_id)
        active = self.bot.db.is_subscription_active(interaction.guild_id)
        embed = discord.Embed(
            title="Status Master SYNC",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Assinatura ativa", value=human_bool(active), inline=True)
        if subscription:
            embed.add_field(name="Plano", value=subscription["plan_name"], inline=True)
            embed.add_field(name="Expira", value=discord_time(subscription["expires_at"], "F"), inline=False)
            embed.add_field(name="Bloqueado", value=human_bool(subscription["locked"]), inline=True)
        else:
            embed.add_field(name="Plano", value="Nao configurado", inline=True)
        embed.add_field(name="Latencia", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.set_footer(text="Master SYNC")
        await respond(interaction, embed, ephemeral=True, icon_name="info", thumbnail=True)

    @app_commands.command(name="ajuda", description="Mostra a ajuda interativa por categoria.")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = build_help_embed("geral")
        files = decorate_embed_with_icon(embed, "info", thumbnail=True, author_name="Central de ajuda")
        await interaction.response.send_message(embed=embed, view=HelpView(), ephemeral=True, **files_kwargs(files))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
