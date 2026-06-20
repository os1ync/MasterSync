from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import Database
from services.config_service import DashboardConfigService
from utils.embed_factory import send_embed_with_icon


def setup_logging() -> None:
    config.ensure_runtime_dirs()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    root.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


class MasterSyncBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        intents.messages = True
        intents.moderation = True

        super().__init__(
            # Slash commands are the public interface. Mention-only prefix keeps
            # room for future text commands while the stored prefix stays in DB.
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )
        self.db: Database
        self.config_service: DashboardConfigService
        self.logger = logging.getLogger("mastersync.bot")

    async def setup_hook(self) -> None:
        self.db = Database(config.DATABASE_PATH, config.SCHEMA_PATH)
        self.db.init_db()
        self.config_service = DashboardConfigService(self.db)
        await self.load_cogs()
        await self.sync_application_commands()

    async def close(self) -> None:
        if hasattr(self, "db"):
            self.db.close()
        await super().close()

    async def load_cogs(self) -> None:
        for path in sorted(config.COGS_DIR.glob("*.py")):
            if path.stem.startswith("_"):
                continue
            extension = f"cogs.{path.stem}"
            try:
                await self.load_extension(extension)
                self.logger.info("Cog carregada: %s", extension)
            except Exception:
                self.logger.exception("Falha ao carregar cog: %s", extension)

    async def sync_application_commands(self) -> None:
        try:
            if config.BOT_GUILD_ID:
                guild = discord.Object(id=config.BOT_GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                self.logger.info(
                    "Slash commands sincronizados no servidor %s: %s",
                    config.BOT_GUILD_ID,
                    len(synced),
                )
            else:
                synced = await self.tree.sync()
                self.logger.info(
                    "Slash commands globais sincronizados: %s",
                    len(synced),
                )
        except Exception:
            self.logger.exception("Falha ao sincronizar slash commands")

    async def on_ready(self) -> None:
        if self.user is None:
            return
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="moderação, diversão e comunidades",
        )
        await self.change_presence(status=discord.Status.online, activity=activity)
        self.logger.info("Online como %s (%s)", self.user, self.user.id)


bot = MasterSyncBot()


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    logger = logging.getLogger("mastersync.errors")
    original = getattr(error, "original", error)

    if isinstance(error, app_commands.CommandOnCooldown):
        description = (
            f"Aguarde **{error.retry_after:.1f}s** antes de usar este comando de novo."
        )
    elif isinstance(error, app_commands.MissingPermissions):
        description = "Você não tem permissão para usar este comando."
    elif isinstance(error, app_commands.BotMissingPermissions):
        description = "Eu não tenho as permissões necessárias para executar esta ação."
    elif isinstance(error, app_commands.CheckFailure):
        description = "Este comando não pode ser usado aqui."
    elif isinstance(original, discord.Forbidden):
        description = (
            "O Discord negou a ação. Confira minhas permissões e posição de cargo."
        )
    elif isinstance(original, discord.NotFound):
        description = "Não encontrei o recurso solicitado. Tente novamente."
    else:
        logger.error(
            "Erro em slash command: %s",
            original,
            exc_info=(type(original), original, original.__traceback__),
        )
        description = "Ocorreu um erro inesperado. O erro foi registrado nos logs."

    message = discord.Embed(
        title="Ops, algo deu errado",
        description=description,
        color=config.ERROR_COLOR,
        timestamp=discord.utils.utcnow(),
    )
    try:
        await send_embed_with_icon(
            interaction,
            message,
            "error",
            ephemeral=True,
            thumbnail=True,
        )
    except discord.HTTPException:
        logger.exception("Falha ao enviar mensagem de erro")


async def run_bot() -> None:
    setup_logging()
    if not config.DISCORD_TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN não foi definido. "
            "Crie um arquivo .env com o token do bot."
        )

    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(run_bot())
