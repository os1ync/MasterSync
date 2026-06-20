from __future__ import annotations

from datetime import datetime, timezone


def seconds_left(last: str | None, cooldown_seconds: int) -> int:
    if not last:
        return 0
    try:
        parsed = datetime.fromisoformat(last)
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - parsed).total_seconds()
    return max(0, int(cooldown_seconds - elapsed))


def cooldown_key(interaction) -> tuple[int | None, int]:
    return (interaction.guild_id, interaction.user.id)
