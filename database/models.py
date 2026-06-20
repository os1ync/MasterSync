from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SubscriptionPlan:
    guild_id: int
    owner_id: int
    plan_name: str
    status: str
    expires_at: str | None
    max_tickets: int
    max_giveaways: int
    casino_enabled: bool
    economy_enabled: bool
    premium_features_enabled: bool
    notes: str | None = None
