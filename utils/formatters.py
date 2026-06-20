from __future__ import annotations

from datetime import datetime, timezone

from config import CURRENCY_SYMBOL


def money(amount: int) -> str:
    return f"{CURRENCY_SYMBOL} {amount:,}".replace(",", ".")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def discord_time(value: str | None, style: str = "F") -> str:
    parsed = parse_dt(value)
    return f"<t:{int(parsed.timestamp())}:{style}>" if parsed else "Nao definido"


def human_bool(value: bool | int) -> str:
    return "Ativo" if bool(value) else "Inativo"
