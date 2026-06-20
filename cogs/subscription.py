from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import error, info, respond, success
from utils.checks import owner_only
from utils.formatters import discord_time, human_bool


PLAN_LIMITS = {
    "starter": {"max_tickets": 25, "max_giveaways": 5, "casino_enabled": 1, "economy_enabled": 1, "premium_features_enabled": 1},
    "standard": {"max_tickets": 75, "max_giveaways": 15, "casino_enabled": 1, "economy_enabled": 1, "premium_features_enabled": 1},
    "premium": {"max_tickets": 150, "max_giveaways": 50, "casino_enabled": 1, "economy_enabled": 1, "premium_features_enabled": 1},
    "enterprise": {"max_tickets": 500, "max_giveaways": 150, "casino_enabled": 1, "economy_enabled": 1, "premium_features_enabled": 1},
}


def parse_guild_id(raw: str) -> int:
    cleaned = raw.strip().replace("<", "").replace(">", "")
    if not cleaned.isdigit():
        raise ValueError("ID de servidor invalido.")
    return int(cleaned)


class Subscription(commands.Cog):
    assinatura = app_commands.Group(name="assinatura", description="Gerenciamento de aluguel mensal do Master SYNC.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @assinatura.command(name="ativar", description="Ativa uma assinatura para um servidor.")
    @app_commands.describe(servidor="ID do servidor.", plano="Nome do plano.", dias="Quantidade de dias de acesso.")
    @owner_only
    async def activate(self, interaction: discord.Interaction, servidor: str, plano: str, dias: app_commands.Range[int, 1, 730]) -> None:
        guild_id = parse_guild_id(servidor)
        guild = self.bot.get_guild(guild_id)
        owner_id = guild.owner_id if guild else 0
        plan = plano.strip()[:50] or "premium"
        limits = PLAN_LIMITS.get(plan.lower(), PLAN_LIMITS["premium"])
        self.bot.db.upsert_subscription(guild_id, owner_id, plan, int(dias), notes=f"Ativado por {interaction.user.id}", **limits)
        await respond(interaction, success("Assinatura ativada", f"Servidor `{guild_id}` ativado no plano **{plan}** por **{dias}** dias."), ephemeral=True, icon_name="success", thumbnail=True)

    @assinatura.command(name="desativar", description="Desativa uma assinatura.")
    @app_commands.describe(servidor="ID do servidor.")
    @owner_only
    async def deactivate(self, interaction: discord.Interaction, servidor: str) -> None:
        guild_id = parse_guild_id(servidor)
        self.bot.db.deactivate_subscription(guild_id, f"Desativado por {interaction.user.id}")
        await respond(interaction, success("Assinatura desativada", f"O servidor `{guild_id}` foi desativado."), ephemeral=True, icon_name="warning", thumbnail=True)

    @assinatura.command(name="renovar", description="Renova uma assinatura existente.")
    @app_commands.describe(servidor="ID do servidor.", dias="Dias adicionais.")
    @owner_only
    async def renew(self, interaction: discord.Interaction, servidor: str, dias: app_commands.Range[int, 1, 730]) -> None:
        guild_id = parse_guild_id(servidor)
        if not self.bot.db.renew_subscription(guild_id, int(dias)):
            await respond(interaction, error("Assinatura nao encontrada", "Ative o servidor antes de renovar."), ephemeral=True)
            return
        await respond(interaction, success("Assinatura renovada", f"O servidor `{guild_id}` recebeu mais **{dias}** dias."), ephemeral=True, icon_name="success", thumbnail=True)

    @assinatura.command(name="status", description="Mostra o status de uma assinatura.")
    @app_commands.describe(servidor="ID do servidor.")
    @owner_only
    async def status(self, interaction: discord.Interaction, servidor: str) -> None:
        guild_id = parse_guild_id(servidor)
        row = self.bot.db.get_subscription(guild_id)
        if row is None:
            await respond(interaction, error("Assinatura nao encontrada", "Nenhuma assinatura registrada para este servidor."), ephemeral=True)
            return
        message = info("Status da assinatura")
        message.add_field(name="Servidor", value=f"`{guild_id}`", inline=True)
        message.add_field(name="Plano", value=row["plan_name"], inline=True)
        message.add_field(name="Status", value=row["status"], inline=True)
        message.add_field(name="Expira em", value=discord_time(row["expires_at"], "F"), inline=False)
        message.add_field(name="Bloqueado", value=human_bool(row["locked"]), inline=True)
        message.add_field(name="Tickets max.", value=str(row["max_tickets"]), inline=True)
        message.add_field(name="Sorteios max.", value=str(row["max_giveaways"]), inline=True)
        message.add_field(name="Observacoes", value=row["notes"] or "Nenhuma", inline=False)
        await respond(interaction, message, ephemeral=True, icon_name="info", thumbnail=True)

    @assinatura.command(name="listar", description="Lista assinaturas registradas.")
    @owner_only
    async def list_subscriptions(self, interaction: discord.Interaction) -> None:
        rows = self.bot.db.list_subscriptions()
        lines = []
        for row in rows[:20]:
            active = "ativo" if self.bot.db.is_subscription_active(row["guild_id"]) else "inativo"
            lines.append(f"`{row['guild_id']}` - {row['plan_name']} - {active} - expira {discord_time(row['expires_at'], 'd')}")
        description = "\n".join(lines) if lines else "Nenhuma assinatura registrada."
        await respond(interaction, info("Assinaturas", description), ephemeral=True, icon_name="info", thumbnail=True)

    @assinatura.command(name="bloquear", description="Bloqueia temporariamente um servidor.")
    @app_commands.describe(servidor="ID do servidor.", motivo="Motivo interno do bloqueio.")
    @owner_only
    async def block(self, interaction: discord.Interaction, servidor: str, motivo: str = "Bloqueio administrativo") -> None:
        guild_id = parse_guild_id(servidor)
        self.bot.db.set_subscription_lock(guild_id, True, motivo[:500])
        await respond(interaction, success("Servidor bloqueado", f"O servidor `{guild_id}` foi bloqueado."), ephemeral=True, icon_name="warning", thumbnail=True)

    @assinatura.command(name="desbloquear", description="Remove o bloqueio de um servidor.")
    @app_commands.describe(servidor="ID do servidor.")
    @owner_only
    async def unblock(self, interaction: discord.Interaction, servidor: str) -> None:
        guild_id = parse_guild_id(servidor)
        self.bot.db.set_subscription_lock(guild_id, False, "Desbloqueado")
        await respond(interaction, success("Servidor desbloqueado", f"O servidor `{guild_id}` foi desbloqueado."), ephemeral=True, icon_name="success", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Subscription(bot))
