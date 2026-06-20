from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from cogs._helpers import error, respond, success
from config import DEFAULT_AVATAR_PATH, EMBED_COLOR, WELCOME_BG_PATH
from utils.checks import premium_required
from utils.icon_map import ICON_MAP
from utils.icons import resolve_icon


CARD_SIZE = (1000, 400)
AVATAR_SIZE = 154


def load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    windows_fonts = Path("C:/Windows/Fonts")
    candidates = [
        windows_fonts / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        windows_fonts / ("arialbd.ttf" if bold else "arial.ttf"),
        windows_fonts / "calibrib.ttf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, *, bold: bool) -> ImageFont.ImageFont:
    size = start_size
    while size >= 18:
        font = load_font(size, bold=bold)
        box = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        if box[2] - box[0] <= max_width:
            return font
        size -= 2
    return load_font(18, bold=bold)


def center_text(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    *,
    fill: tuple[int, int, int],
    stroke_fill: tuple[int, int, int] = (0, 0, 0),
    stroke_width: int = 2,
) -> None:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    width = box[2] - box[0]
    draw.text(
        ((CARD_SIZE[0] - width) / 2, y),
        text,
        font=font,
        fill=fill,
        stroke_fill=stroke_fill,
        stroke_width=stroke_width,
    )


def load_card_icon(icon_path, size: int) -> Image.Image | None:
    if isinstance(icon_path, str):
        icon_path = ICON_MAP.get(icon_path, icon_path)
    path = resolve_icon(icon_path)
    if path is None:
        return None
    try:
        icon = Image.open(path).convert("RGBA")
    except OSError:
        return None
    return ImageOps.contain(icon, (size, size))


def center_text_with_icon(
    base: Image.Image,
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    *,
    icon: Image.Image | None = None,
    gap: int = 12,
    fill: tuple[int, int, int],
    stroke_fill: tuple[int, int, int] = (0, 0, 0),
    stroke_width: int = 2,
) -> None:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    icon_width = icon.width if icon else 0
    total_width = text_width + (gap + icon_width if icon else 0)
    x = (CARD_SIZE[0] - total_width) / 2

    if icon:
        icon_y = int(y + (text_height - icon.height) / 2 + 4)
        base.alpha_composite(icon, (int(x), icon_y))
        x += icon.width + gap

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_fill=stroke_fill,
        stroke_width=stroke_width,
    )


def fallback_background() -> Image.Image:
    base = Image.new("RGB", CARD_SIZE, (8, 12, 28))
    draw = ImageDraw.Draw(base)
    for y in range(CARD_SIZE[1]):
        ratio = y / CARD_SIZE[1]
        color = (
            int(9 + ratio * 8),
            int(18 + ratio * 18),
            int(46 + ratio * 38),
        )
        draw.line([(0, y), (CARD_SIZE[0], y)], fill=color)
    draw.rectangle((0, 290, 1000, 400), fill=(5, 34, 44))
    draw.polygon([(0, 275), (170, 160), (340, 276)], fill=(11, 52, 72))
    draw.polygon([(620, 280), (820, 130), (1000, 278)], fill=(19, 60, 90))
    return base


def load_background(guild_id: int | None = None) -> Image.Image:
    if guild_id is not None:
        custom = WELCOME_BG_PATH.with_name(f"welcome_bg_{guild_id}.png")
        if custom.exists():
            return Image.open(custom).convert("RGB")
    if WELCOME_BG_PATH.exists():
        return Image.open(WELCOME_BG_PATH).convert("RGB")
    return fallback_background()


def circular_avatar(source: Image.Image) -> Image.Image:
    avatar = ImageOps.fit(source.convert("RGBA"), (AVATAR_SIZE, AVATAR_SIZE), centering=(0.5, 0.5))
    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1), fill=255)
    avatar.putalpha(mask)
    return avatar


def circular_image(source: Image.Image, size: int) -> Image.Image:
    image = ImageOps.fit(source.convert("RGBA"), (size, size), centering=(0.5, 0.5))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    image.putalpha(mask)
    return image


class Welcome(commands.Cog):
    welcome = app_commands.Group(name="boasvindas", description="Configure o sistema de boas-vindas.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_avatar_image(self, member: discord.Member) -> Image.Image:
        try:
            data = await member.display_avatar.with_size(256).read()
            return Image.open(BytesIO(data)).convert("RGBA")
        except Exception:
            if DEFAULT_AVATAR_PATH.exists():
                return Image.open(DEFAULT_AVATAR_PATH).convert("RGBA")
        return Image.new("RGBA", (256, 256), (24, 35, 68, 255))

    async def get_server_icon_image(self, guild: discord.Guild) -> Image.Image | None:
        if guild.icon is None:
            return None
        try:
            data = await guild.icon.with_size(128).read()
            return Image.open(BytesIO(data)).convert("RGBA")
        except Exception:
            return None

    async def build_welcome_file(self, member: discord.Member, member_number: int) -> discord.File:
        background = ImageOps.fit(load_background(member.guild.id), CARD_SIZE, centering=(0.5, 0.5)).convert("RGBA")
        blurred = background.filter(ImageFilter.GaussianBlur(1.2))
        background = Image.blend(background, blurred, 0.18)

        overlay = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle((0, 0, 1000, 400), fill=(2, 6, 18, 95))
        draw.rounded_rectangle(
            (58, 38, 942, 362),
            radius=32,
            fill=(2, 8, 20, 115),
            outline=(91, 205, 250, 150),
            width=2,
        )
        draw.ellipse((410, 52, 590, 232), fill=(103, 58, 183, 85), outline=(91, 205, 250, 180), width=4)
        background.alpha_composite(overlay)

        server_icon = await self.get_server_icon_image(member.guild)
        if server_icon is not None:
            server_badge_size = 58
            server_badge = circular_image(server_icon, server_badge_size)
            badge_ring = Image.new("RGBA", (server_badge_size + 10, server_badge_size + 10), (0, 0, 0, 0))
            ring_draw = ImageDraw.Draw(badge_ring)
            ring_draw.ellipse((0, 0, badge_ring.width - 1, badge_ring.height - 1), fill=(2, 8, 20, 130), outline=(91, 205, 250, 160), width=2)
            badge_ring.alpha_composite(server_badge, (5, 5))
            background.alpha_composite(badge_ring, (850, 62))

        avatar = circular_avatar(await self.get_avatar_image(member))
        ring = Image.new("RGBA", (AVATAR_SIZE + 18, AVATAR_SIZE + 18), (0, 0, 0, 0))
        ring_draw = ImageDraw.Draw(ring)
        ring_draw.ellipse((0, 0, AVATAR_SIZE + 17, AVATAR_SIZE + 17), fill=(124, 58, 237, 255))
        ring_draw.ellipse((5, 5, AVATAR_SIZE + 12, AVATAR_SIZE + 12), fill=(44, 212, 255, 255))
        ring_draw.ellipse((9, 9, AVATAR_SIZE + 8, AVATAR_SIZE + 8), fill=(2, 8, 20, 255))
        background.alpha_composite(ring, (CARD_SIZE[0] // 2 - ring.width // 2, 48))
        background.alpha_composite(avatar, (CARD_SIZE[0] // 2 - AVATAR_SIZE // 2, 57))

        draw = ImageDraw.Draw(background)
        display_name = member.display_name[:26]
        title = f"BEM-VINDO(A), @{display_name}!"
        subtitle = f"Veteranos Gamming - Membro #{member_number}"
        title_font = fit_font(draw, title, 860, 46, bold=True)
        subtitle_font = fit_font(draw, subtitle, 820, 28, bold=False)
        welcome_icon = load_card_icon("welcome", 38)
        member_icon = load_card_icon("user", 25)

        center_text_with_icon(background, draw, 248, title, title_font, icon=welcome_icon, fill=(245, 250, 255), stroke_fill=(2, 8, 20), stroke_width=3)
        center_text_with_icon(background, draw, 306, subtitle, subtitle_font, icon=member_icon, gap=9, fill=(165, 231, 255), stroke_fill=(2, 8, 20), stroke_width=2)

        buffer = BytesIO()
        background.convert("RGB").save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return discord.File(buffer, filename="mastersync_welcome.png")

    async def send_welcome(self, channel: discord.TextChannel, member: discord.Member) -> None:
        settings = self.bot.config_service.get_guild_config(member.guild.id)
        member_number = member.guild.member_count or len(member.guild.members)
        file = await self.build_welcome_file(member, member_number)
        placeholders = {
            "mention": member.mention,
            "user_mention": member.mention,
            "user": member.name,
            "server": member.guild.name,
            "member_number": member_number,
            "member_count": member_number,
        }
        template = settings["welcome_message"] or "Bem-Vindo(a) {mention}.\nVoce e o membro numero #{member_number} do servidor."
        try:
            content = template.format(**placeholders)
        except (KeyError, IndexError, ValueError):
            content = "Bem-Vindo(a) {mention}.\nVoce e o membro numero #{member_number} do servidor.".format(**placeholders)
        view = None
        if settings["welcome_rules_url"]:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Ver regras", url=settings["welcome_rules_url"]))
        if settings["welcome_embed_enabled"]:
            embed = success("Boas-vindas", content)
            await channel.send(file=file, embed=embed, view=view)
        else:
            await channel.send(content=content, file=file, view=view)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if not self.bot.db.is_subscription_active(member.guild.id):
            return
        settings = self.bot.config_service.get_guild_config(member.guild.id)
        if not settings["welcome_enabled"] or not settings["welcome_channel_id"]:
            return

        channel = member.guild.get_channel(settings["welcome_channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            await self.send_welcome(channel, member)
        except discord.HTTPException:
            return

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if not self.bot.db.is_subscription_active(member.guild.id):
            return
        settings = self.bot.config_service.get_guild_config(member.guild.id)
        if not settings["leave_enabled"]:
            return
        channel = member.guild.get_channel(settings["leave_channel_id"] or settings["welcome_channel_id"] or 0)
        if not isinstance(channel, discord.TextChannel):
            return
        placeholders = {
            "mention": member.mention,
            "user_mention": member.mention,
            "user": member.name,
            "server": member.guild.name,
            "member_number": member.guild.member_count or 0,
            "member_count": member.guild.member_count or 0,
        }
        try:
            text = (settings["leave_message"] or "{user} saiu do servidor.").format(**placeholders)
        except (KeyError, IndexError, ValueError):
            text = "{user} saiu do servidor.".format(**placeholders)
        try:
            await channel.send(text)
        except discord.HTTPException:
            return

    @welcome.command(name="canal", description="Define o canal onde as boas-vindas serão enviadas.")
    @app_commands.describe(canal="Canal de texto para receber as boas-vindas.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def welcome_channel(self, interaction: discord.Interaction, canal: discord.TextChannel) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_channel_id", canal.id)
        await respond(interaction, success("Boas-vindas configuradas", f"As mensagens serao enviadas em {canal.mention}."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @welcome.command(name="configurar", description="Configura canal e status das boas-vindas.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def welcome_configure(self, interaction: discord.Interaction, canal: discord.TextChannel, ativo: bool = True, embed: bool = False, regras_url: str | None = None) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_channel_id", canal.id)
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_enabled", 1 if ativo else 0)
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_embed_enabled", 1 if embed else 0)
        if regras_url:
            self.bot.db.update_guild_setting(interaction.guild_id, "welcome_rules_url", regras_url[:500])
        await respond(interaction, success("Boas-vindas configuradas", "Configuracoes premium de boas-vindas foram salvas."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @welcome.command(name="mensagem", description="Define o texto de boas-vindas.")
    @app_commands.describe(texto="Use {mention}, {user}, {server} e {member_number}.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def welcome_message(self, interaction: discord.Interaction, texto: str) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_message", texto[:1500])
        await respond(interaction, success("Mensagem salva", "Texto de boas-vindas atualizado."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @welcome.command(name="fundo", description="Envia uma imagem para usar como fundo de boas-vindas.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def welcome_background(self, interaction: discord.Interaction, imagem: discord.Attachment) -> None:
        if not (imagem.content_type or "").startswith("image/"):
            await respond(interaction, error("Arquivo invalido", "Envie uma imagem PNG ou JPG."), ephemeral=True)
            return
        if imagem.size and imagem.size > 8 * 1024 * 1024:
            await respond(interaction, error("Arquivo muito grande", "Use uma imagem com ate 8 MB."), ephemeral=True)
            return
        target = WELCOME_BG_PATH.with_name(f"welcome_bg_{interaction.guild_id}.png")
        await imagem.save(target)
        await respond(interaction, success("Fundo atualizado", "Imagem de fundo personalizada salva para este servidor."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @welcome.command(name="saida", description="Ativa ou desativa mensagem de saida.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def leave_toggle(self, interaction: discord.Interaction, estado: Literal["ativar", "desativar"], canal: discord.TextChannel | None = None) -> None:
        enabled = estado == "ativar"
        self.bot.db.update_guild_setting(interaction.guild_id, "leave_enabled", 1 if enabled else 0)
        if canal:
            self.bot.db.update_guild_setting(interaction.guild_id, "leave_channel_id", canal.id)
        await respond(interaction, success("Saida atualizada", f"Mensagens de saida: {'ativas' if enabled else 'inativas'}."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @welcome.command(name="resetar", description="Reseta configuracoes de boas-vindas.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def welcome_reset(self, interaction: discord.Interaction) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_message", "Bem-Vindo(a) {mention}.\nVoce e o membro numero #{member_number} do servidor.")
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_embed_enabled", 0)
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_rules_url", None)
        custom = WELCOME_BG_PATH.with_name(f"welcome_bg_{interaction.guild_id}.png")
        if custom.exists():
            custom.unlink()
        await respond(interaction, success("Boas-vindas resetadas", "As configuracoes foram restauradas para o padrao."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @welcome.command(name="ativar", description="Ativa o sistema de boas-vindas.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def welcome_enable(self, interaction: discord.Interaction) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_enabled", 1)
        await respond(interaction, success("Boas-vindas ativadas", "Novos membros receberao a mensagem premium do Master SYNC."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @welcome.command(name="desativar", description="Desativa o sistema de boas-vindas.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def welcome_disable(self, interaction: discord.Interaction) -> None:
        self.bot.db.update_guild_setting(interaction.guild_id, "welcome_enabled", 0)
        await respond(interaction, success("Boas-vindas desativadas", "O envio automatico foi pausado para este servidor."), ephemeral=True, icon_name="welcome", thumbnail=True)

    @welcome.command(name="testar", description="Envia uma prévia da mensagem de boas-vindas.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @premium_required
    async def welcome_test(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        settings = self.bot.config_service.get_guild_config(interaction.guild_id)
        channel = interaction.guild.get_channel(settings["welcome_channel_id"] or 0)
        if not isinstance(channel, discord.TextChannel):
            channel = interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None
        if channel is None:
            await respond(interaction, error("Canal invalido", "Configure um canal com `/boasvindas canal` antes de testar."), ephemeral=True)
            return

        await self.send_welcome(channel, interaction.user)
        await respond(interaction, success("Teste enviado", f"A previa foi enviada em {channel.mention}."), ephemeral=True, icon_name="welcome", thumbnail=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
