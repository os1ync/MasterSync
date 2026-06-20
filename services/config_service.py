from __future__ import annotations

from typing import Any


ID_KEYS = {
    "welcome_channel_id",
    "leave_channel_id",
    "logs_channel_id",
    "autorole_role_id",
    "ticket_category_id",
    "ticket_support_role_id",
    "ticket_logs_channel_id",
}


class DashboardConfigService:
    """Reads dashboard guild_configs while preserving guild_settings fallback."""

    DASHBOARD_TO_BOT_KEYS = {
        "tickets_category_id": "ticket_category_id",
        "tickets_support_role_id": "ticket_support_role_id",
    }

    def __init__(self, db):
        self.db = db

    def get_guild_config(self, guild_id: int) -> dict[str, Any]:
        base = dict(self.db.get_guild_settings(guild_id))
        dashboard = self.db.fetchone("SELECT * FROM guild_configs WHERE guild_id = ?", (str(guild_id),))
        if dashboard is None:
            return self._normalize(base)

        merged = dict(base)
        for key, value in dict(dashboard).items():
            if value is None:
                continue
            target_key = self.DASHBOARD_TO_BOT_KEYS.get(key, key)
            merged[target_key] = value
        return self._normalize(merged)

    def _normalize(self, config: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(config)
        for key in ID_KEYS:
            value = normalized.get(key)
            if isinstance(value, str):
                normalized[key] = int(value) if value.isdigit() else None
        return normalized

