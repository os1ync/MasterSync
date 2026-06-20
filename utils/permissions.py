from __future__ import annotations

import discord


def is_guild_admin(member: discord.Member | discord.User) -> bool:
    return isinstance(member, discord.Member) and member.guild_permissions.administrator


def hierarchy_allows(actor: discord.Member, target: discord.Member) -> bool:
    if actor.guild.owner_id == actor.id:
        return True
    return actor.top_role > target.top_role


def bot_can_manage(bot_member: discord.Member | None, target: discord.Member) -> bool:
    return bool(bot_member and hierarchy_allows(bot_member, target))
