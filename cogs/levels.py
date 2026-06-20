from __future__ import annotations

import random
from io import BytesIO
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from cogs._helpers import error, respond, success
from database.db import utc_now_iso
from utils.checks import feature_required


def required_xp(level: int) -> int:
    return 100 + (level * 75)


class Levels(commands.Cog):
    levels = app_commands.Group(name="levels", description="Configuracao do sistema de niveis.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        if not self.bot.db.feature_enabled(message.guild.id, "levels"):
            return
        settings = self.bot.db.get_guild_settings(message.guild.id)
        if not settings["levels_enabled"]:
            return

        row = self.bot.db.fetchone("SELECT * FROM levels WHERE guild_id = ? AND user_id = ?", (message.guild.id, message.author.id))
        now = utc_now_iso()
        if row and row["last_xp"]:
            parsed = self.bot.db._parse_datetime(row["last_xp"])
            if parsed and (discord.utils.utcnow() - parsed).total_seconds() < 45:
                return
        if row is None:
            self.bot.db.execute("INSERT INTO levels (guild_id, user_id, xp, level, last_xp) VALUES (?, ?, 0, 0, ?)", (message.guild.id, message.author.id, now))
            row = self.bot.db.fetchone("SELECT * FROM levels WHERE guild_id = ? AND user_id = ?", (message.guild.id, message.author.id))

        xp = int(row["xp"]) + random.randint(12, 22)
        level = int(row["level"])
        leveled = False
        while xp >= required_xp(level):
            xp -= required_xp(level)
            level += 1
            leveled = True
        self.bot.db.execute("UPDATE levels SET xp = ?, level = ?, last_xp = ? WHERE guild_id = ? AND user_id = ?", (xp, level, now, message.guild.id, message.author.id))

        if leveled:
            reward = 100 + level * 25
            self.bot.db.add_wallet(message.guild.id, message.author.id, reward)
            role_row = self.bot.db.fetchone("SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?", (message.guild.id, level))
            if role_row:
                role = message.guild.get_role(role_row["role_id"])
                if role and isinstance(message.author, discord.Member):
                    try:
                        await message.author.add_roles(role, reason="Recompensa de nivel Master SYNC")
                    except discord.HTTPException:
                        pass
            await message.channel.send(f"{message.author.mention} subiu para o nivel **{level}** e recebeu **M$ {reward}**.")

    async def build_level_card(self, member: discord.Member, level: int, xp: int) -> discord.File:
        image = Image.new("RGB", (900, 280), (9, 12, 30))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((28, 28, 872, 252), radius=24, fill=(18, 24, 54), outline=(124, 58, 237), width=3)
        try:
            avatar_data = await member.display_avatar.with_size(128).read()
            avatar = Image.open(BytesIO(avatar_data)).convert("RGB").resize((128, 128))
            image.paste(avatar, (70, 76))
        except Exception:
            pass
        font_big = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 42) if Path("C:/Windows/Fonts/segoeuib.ttf").exists() else ImageFont.load_default()
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 28) if Path("C:/Windows/Fonts/segoeui.ttf").exists() else ImageFont.load_default()
        draw.text((230, 72), member.display_name, fill=(245, 250, 255), font=font_big)
        draw.text((230, 132), f"Nivel {level} - XP {xp}/{required_xp(level)}", fill=(165, 231, 255), font=font)
        bar_w = 560
        progress = min(1, xp / max(1, required_xp(level)))
        draw.rounded_rectangle((230, 184, 230 + bar_w, 214), radius=15, fill=(31, 41, 75))
        draw.rounded_rectangle((230, 184, 230 + int(bar_w * progress), 214), radius=15, fill=(56, 189, 248))
        buf = BytesIO()
        image.save(buf, "PNG")
        buf.seek(0)
        return discord.File(buf, filename="level_card.png")

    @app_commands.command(name="level", description="Mostra seu nivel ou o nivel de outro usuario.")
    @app_commands.guild_only()
    @feature_required("levels")
    async def level(self, interaction: discord.Interaction, usuario: discord.Member | None = None) -> None:
        target = usuario or interaction.user
        row = self.bot.db.fetchone("SELECT * FROM levels WHERE guild_id = ? AND user_id = ?", (interaction.guild_id, target.id))
        level = int(row["level"]) if row else 0
        xp = int(row["xp"]) if row else 0
        file = await self.build_level_card(target, level, xp)
        await interaction.response.send_message(file=file)

    @app_commands.command(name="rank", description="Mostra o ranking de niveis do servidor.")
    @app_commands.guild_only()
    @feature_required("levels")
    async def rank(self, interaction: discord.Interaction) -> None:
        rows = self.bot.db.fetchall("SELECT * FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10", (interaction.guild_id,))
        lines = []
        for idx, row in enumerate(rows, 1):
            lines.append(f"`#{idx}` <@{row['user_id']}> - nivel **{row['level']}** ({row['xp']} XP)")
        await respond(interaction, success("Ranking de niveis", "\n".join(lines) if lines else "Ainda nao ha dados de nivel."), icon_name="ranking", thumbnail=True)

    @levels.command(name="configurar", description="Ativa ou desativa o sistema de niveis.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("levels")
    async def configure(self, interaction: discord.Interaction, estado: bool) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "levels_enabled", 1 if estado else 0)
        await respond(interaction, success("Niveis atualizados", f"Sistema de niveis: {'ativo' if estado else 'inativo'}."), ephemeral=True, icon_name="ranking", thumbnail=True)

    @levels.command(name="cargo", description="Define cargo por nivel.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    @feature_required("levels")
    async def level_role(self, interaction: discord.Interaction, nivel: app_commands.Range[int, 1, 500], cargo: discord.Role) -> None:
        self.bot.db.execute(
            "INSERT INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?) ON CONFLICT(guild_id, level) DO UPDATE SET role_id = excluded.role_id",
            (interaction.guild_id, int(nivel), cargo.id),
        )
        await respond(interaction, success("Cargo por nivel salvo", f"Nivel **{nivel}** entregara {cargo.mention}."), ephemeral=True, icon_name="ranking", thumbnail=True)

    @levels.command(name="reset", description="Reseta o nivel de um usuario.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @feature_required("levels")
    async def reset(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        self.bot.db.execute("DELETE FROM levels WHERE guild_id = ? AND user_id = ?", (interaction.guild_id, usuario.id))
        await respond(interaction, success("Nivel resetado", f"O nivel de {usuario.mention} foi resetado."), ephemeral=True, icon_name="ranking", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Levels(bot))
