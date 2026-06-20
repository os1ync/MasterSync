from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    """Thin SQLite wrapper used by the cogs.

    The bot is mostly I/O bound, but command callbacks can overlap. A re-entrant
    lock keeps multi-step balance updates atomic from Python's side while SQLite
    handles persistence.
    """

    SETTINGS_COLUMNS = {
        "welcome_channel_id",
        "welcome_enabled",
        "welcome_message",
        "welcome_embed_enabled",
        "welcome_rules_url",
        "leave_channel_id",
        "leave_enabled",
        "leave_message",
        "logs_channel_id",
        "logs_enabled",
        "casino_enabled",
        "economy_enabled",
        "tickets_enabled",
        "levels_enabled",
        "giveaways_enabled",
        "automod_enabled",
        "antiraid_enabled",
        "autorole_enabled",
        "autorole_delay",
        "ticket_category_id",
        "ticket_support_role_id",
        "ticket_logs_channel_id",
        "ticket_limit_per_user",
        "casino_min_bet",
        "casino_max_bet",
        "casino_daily_loss_limit",
        "casino_house_edge_percent",
        "prefix",
    }
    COOLDOWN_COLUMNS = {"last_daily", "last_work", "work_boost_until", "casino_multiplier_until", "robbery_protection_until"}

    def __init__(self, database_path: Path, schema_path: Path):
        self.database_path = database_path
        self.schema_path = schema_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")

    def init_db(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._lock, self.connection:
            self.connection.executescript(schema)
            self._migrate_existing_schema()
            self._seed_shop_items()

    def _table_columns(self, table: str) -> set[str]:
        rows = self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        return {row["name"] for row in rows}

    def _add_missing_columns(self, table: str, columns: dict[str, str]) -> None:
        existing = self._table_columns(table)
        for name, definition in columns.items():
            if name not in existing:
                self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def _migrate_existing_schema(self) -> None:
        self._add_missing_columns(
            "guild_settings",
            {
                "welcome_message": "TEXT DEFAULT 'Bem-Vindo(a) {mention}.\\nVoce e o membro numero #{member_number} do servidor.'",
                "welcome_embed_enabled": "INTEGER NOT NULL DEFAULT 0",
                "welcome_rules_url": "TEXT",
                "leave_channel_id": "INTEGER",
                "leave_enabled": "INTEGER NOT NULL DEFAULT 0",
                "leave_message": "TEXT DEFAULT '{user} saiu do servidor.'",
                "logs_enabled": "INTEGER NOT NULL DEFAULT 1",
                "tickets_enabled": "INTEGER NOT NULL DEFAULT 1",
                "levels_enabled": "INTEGER NOT NULL DEFAULT 1",
                "giveaways_enabled": "INTEGER NOT NULL DEFAULT 1",
                "automod_enabled": "INTEGER NOT NULL DEFAULT 0",
                "antiraid_enabled": "INTEGER NOT NULL DEFAULT 0",
                "autorole_enabled": "INTEGER NOT NULL DEFAULT 0",
                "autorole_delay": "INTEGER NOT NULL DEFAULT 0",
                "ticket_category_id": "INTEGER",
                "ticket_support_role_id": "INTEGER",
                "ticket_logs_channel_id": "INTEGER",
                "ticket_limit_per_user": "INTEGER NOT NULL DEFAULT 1",
                "casino_min_bet": "INTEGER NOT NULL DEFAULT 10",
                "casino_max_bet": "INTEGER NOT NULL DEFAULT 50000",
                "casino_daily_loss_limit": "INTEGER NOT NULL DEFAULT 0",
                "casino_house_edge_percent": "REAL NOT NULL DEFAULT 0",
            },
        )
        self._add_missing_columns(
            "users",
            {
                "work_boost_until": "TEXT",
                "casino_multiplier_until": "TEXT",
                "robbery_protection_until": "TEXT",
            },
        )
        self._add_missing_columns(
            "guild_subscriptions",
            {
                "owner_id": "INTEGER NOT NULL DEFAULT 0",
                "plan_name": "TEXT NOT NULL DEFAULT 'inactive'",
                "status": "TEXT NOT NULL DEFAULT 'inactive'",
                "expires_at": "TEXT",
                "max_tickets": "INTEGER NOT NULL DEFAULT 0",
                "max_giveaways": "INTEGER NOT NULL DEFAULT 0",
                "casino_enabled": "INTEGER NOT NULL DEFAULT 0",
                "economy_enabled": "INTEGER NOT NULL DEFAULT 0",
                "premium_features_enabled": "INTEGER NOT NULL DEFAULT 0",
                "locked": "INTEGER NOT NULL DEFAULT 0",
                "notes": "TEXT",
                "created_at": "TEXT",
                "updated_at": "TEXT",
            },
        )
        self._add_missing_columns(
            "tickets",
            {
                "channel_id": "INTEGER",
                "claimed_by": "INTEGER",
                "status": "TEXT NOT NULL DEFAULT 'open'",
                "reason": "TEXT",
                "blocked": "INTEGER NOT NULL DEFAULT 0",
                "closed_at": "TEXT",
                "closed_by": "INTEGER",
            },
        )
        self._add_missing_columns(
            "automod_settings",
            {
                "anti_caps": "INTEGER NOT NULL DEFAULT 0",
                "anti_mentions": "INTEGER NOT NULL DEFAULT 0",
                "banned_words": "TEXT",
                "punishment": "TEXT NOT NULL DEFAULT 'delete'",
                "whitelist_channels": "TEXT",
                "whitelist_roles": "TEXT",
            },
        )

    def _seed_shop_items(self) -> None:
        items = [
            ("work_booster", "Booster de trabalho", "Aumenta os ganhos do /trabalhar por 24 horas.", 2500),
            ("mystery_box", "Caixa misteriosa", "Entrega uma recompensa aleatoria em MasterCoins.", 1800),
            ("vip_ticket", "Ticket VIP simbolico", "Item colecionavel para eventos e beneficios manuais.", 5000),
            ("robbery_protection", "Protecao contra roubo", "Protecao simbolica para futuras mecanicas de roubo.", 2200),
            ("casino_multiplier", "Multiplicador de cassino", "Aumenta lucros de apostas vencedoras em 25% por 12 horas.", 4500),
        ]
        for key, name, description, price in items:
            self.connection.execute(
                """
                INSERT INTO shop_items (guild_id, key, name, description, price, active)
                VALUES (0, ?, ?, ?, ?, 1)
                ON CONFLICT(guild_id, key) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    price = excluded.price,
                    active = 1
                """,
                (key, name, description, price),
            )

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def fetchone(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(query, tuple(params)).fetchone()

    def fetchall(self, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.connection.execute(query, tuple(params)).fetchall())

    def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        with self._lock, self.connection:
            self.connection.execute(query, tuple(params))

    def ensure_guild(self, guild_id: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
            (guild_id,),
        )

    def get_guild_settings(self, guild_id: int) -> sqlite3.Row:
        self.ensure_guild(guild_id)
        row = self.fetchone(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        )
        if row is None:
            raise RuntimeError(f"Could not create settings for guild {guild_id}")
        return row

    def update_guild_setting(self, guild_id: int, column: str, value: Any) -> None:
        if column not in self.SETTINGS_COLUMNS:
            raise ValueError(f"Invalid guild setting column: {column}")
        self.ensure_guild(guild_id)
        self.execute(
            f"UPDATE guild_settings SET {column} = ? WHERE guild_id = ?",
            (value, guild_id),
        )

    def ensure_user(self, guild_id: int, user_id: int) -> None:
        self.ensure_guild(guild_id)
        self.execute(
            """
            INSERT OR IGNORE INTO users (user_id, guild_id, created_at)
            VALUES (?, ?, ?)
            """,
            (user_id, guild_id, utc_now_iso()),
        )

    def get_user(self, guild_id: int, user_id: int) -> sqlite3.Row:
        self.ensure_user(guild_id, user_id)
        row = self.fetchone(
            "SELECT * FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        if row is None:
            raise RuntimeError(f"Could not create economy profile for user {user_id}")
        return row

    def add_wallet(self, guild_id: int, user_id: int, amount: int, *, count_stats: bool = True) -> None:
        self.ensure_user(guild_id, user_id)
        earned = max(amount, 0) if count_stats else 0
        lost = abs(min(amount, 0)) if count_stats else 0
        with self._lock, self.connection:
            self.connection.execute(
                """
                UPDATE users
                SET wallet = wallet + ?,
                    total_earned = total_earned + ?,
                    total_lost = total_lost + ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (amount, earned, lost, guild_id, user_id),
            )

    def set_cooldown(self, guild_id: int, user_id: int, column: str, value: str | None) -> None:
        if column not in self.COOLDOWN_COLUMNS:
            raise ValueError(f"Invalid cooldown column: {column}")
        self.ensure_user(guild_id, user_id)
        self.execute(
            f"UPDATE users SET {column} = ? WHERE guild_id = ? AND user_id = ?",
            (value, guild_id, user_id),
        )

    def transfer_wallet(self, guild_id: int, payer_id: int, receiver_id: int, amount: int) -> bool:
        self.ensure_user(guild_id, payer_id)
        self.ensure_user(guild_id, receiver_id)
        with self._lock, self.connection:
            payer = self.connection.execute(
                "SELECT wallet FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, payer_id),
            ).fetchone()
            if payer is None or payer["wallet"] < amount:
                return False
            self.connection.execute(
                "UPDATE users SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?",
                (amount, guild_id, payer_id),
            )
            self.connection.execute(
                "UPDATE users SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?",
                (amount, guild_id, receiver_id),
            )
            return True

    def deposit(self, guild_id: int, user_id: int, amount: int) -> bool:
        self.ensure_user(guild_id, user_id)
        with self._lock, self.connection:
            row = self.connection.execute(
                "SELECT wallet FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            if row is None or row["wallet"] < amount:
                return False
            self.connection.execute(
                """
                UPDATE users
                SET wallet = wallet - ?, bank = bank + ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (amount, amount, guild_id, user_id),
            )
            return True

    def withdraw(self, guild_id: int, user_id: int, amount: int) -> bool:
        self.ensure_user(guild_id, user_id)
        with self._lock, self.connection:
            row = self.connection.execute(
                "SELECT bank FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            if row is None or row["bank"] < amount:
                return False
            self.connection.execute(
                """
                UPDATE users
                SET wallet = wallet + ?, bank = bank - ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (amount, amount, guild_id, user_id),
            )
            return True

    def get_top_users(self, guild_id: int, limit: int = 10) -> list[sqlite3.Row]:
        self.ensure_guild(guild_id)
        return self.fetchall(
            """
            SELECT *, (wallet + bank) AS total
            FROM users
            WHERE guild_id = ?
            ORDER BY total DESC, wallet DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )

    def record_casino_history(
        self,
        guild_id: int,
        user_id: int,
        game: str,
        bet: int,
        result: str,
        profit: int,
    ) -> None:
        self.ensure_guild(guild_id)
        self.execute(
            """
            INSERT INTO casino_history (guild_id, user_id, game, bet, result, profit, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, game, bet, result, profit, utc_now_iso()),
        )

    def settle_instant_casino(
        self,
        guild_id: int,
        user_id: int,
        game: str,
        bet: int,
        result: str,
        payout: int,
    ) -> int | None:
        """Settle a complete game in one transaction.

        payout is the total amount returned to the player. For a loss it is 0,
        for a tie it is equal to bet, and for a win it includes the stake.
        """

        self.ensure_user(guild_id, user_id)
        profit = payout - bet
        earned = max(profit, 0)
        lost = abs(min(profit, 0))

        with self._lock, self.connection:
            row = self.connection.execute(
                "SELECT wallet FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            if row is None or row["wallet"] < bet:
                return None

            self.connection.execute(
                """
                UPDATE users
                SET wallet = wallet + ?,
                    total_earned = total_earned + ?,
                    total_lost = total_lost + ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (profit, earned, lost, guild_id, user_id),
            )
            self.connection.execute(
                """
                INSERT INTO casino_history (guild_id, user_id, game, bet, result, profit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, game, bet, result, profit, utc_now_iso()),
            )
            return profit

    def reserve_casino_bet(self, guild_id: int, user_id: int, bet: int) -> bool:
        self.ensure_user(guild_id, user_id)
        with self._lock, self.connection:
            row = self.connection.execute(
                "SELECT wallet FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            if row is None or row["wallet"] < bet:
                return False
            self.connection.execute(
                "UPDATE users SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?",
                (bet, guild_id, user_id),
            )
            return True

    def settle_reserved_casino_bet(
        self,
        guild_id: int,
        user_id: int,
        game: str,
        bet: int,
        result: str,
        payout: int,
    ) -> int:
        self.ensure_user(guild_id, user_id)
        profit = payout - bet
        earned = max(profit, 0)
        lost = abs(min(profit, 0))
        with self._lock, self.connection:
            self.connection.execute(
                """
                UPDATE users
                SET wallet = wallet + ?,
                    total_earned = total_earned + ?,
                    total_lost = total_lost + ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (payout, earned, lost, guild_id, user_id),
            )
            self.connection.execute(
                """
                INSERT INTO casino_history (guild_id, user_id, game, bet, result, profit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, game, bet, result, profit, utc_now_iso()),
            )
            return profit

    def get_casino_stats(self, guild_id: int, user_id: int) -> sqlite3.Row:
        self.ensure_user(guild_id, user_id)
        row = self.fetchone(
            """
            SELECT
                COUNT(*) AS games,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) AS losses,
                COALESCE(SUM(profit), 0) AS net_profit
            FROM casino_history
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        if row is None:
            raise RuntimeError("Could not read casino stats")
        return row

    # Subscription and feature gates
    def get_subscription(self, guild_id: int) -> sqlite3.Row | None:
        return self.fetchone("SELECT * FROM guild_subscriptions WHERE guild_id = ?", (guild_id,))

    def upsert_subscription(
        self,
        guild_id: int,
        owner_id: int,
        plan_name: str,
        days: int,
        *,
        notes: str | None = None,
        max_tickets: int = 100,
        max_giveaways: int = 25,
        casino_enabled: int = 1,
        economy_enabled: int = 1,
        premium_features_enabled: int = 1,
    ) -> None:
        now = utc_now_iso()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=max(days, 1))).isoformat()
        self.ensure_guild(guild_id)
        self.execute(
            """
            INSERT INTO guild_subscriptions (
                guild_id, owner_id, plan_name, status, expires_at, max_tickets,
                max_giveaways, casino_enabled, economy_enabled, premium_features_enabled,
                locked, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                owner_id = excluded.owner_id,
                plan_name = excluded.plan_name,
                status = 'active',
                expires_at = excluded.expires_at,
                max_tickets = excluded.max_tickets,
                max_giveaways = excluded.max_giveaways,
                casino_enabled = excluded.casino_enabled,
                economy_enabled = excluded.economy_enabled,
                premium_features_enabled = excluded.premium_features_enabled,
                locked = 0,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                guild_id,
                owner_id,
                plan_name,
                expires_at,
                max_tickets,
                max_giveaways,
                casino_enabled,
                economy_enabled,
                premium_features_enabled,
                notes,
                now,
                now,
            ),
        )

    def deactivate_subscription(self, guild_id: int, notes: str | None = None) -> None:
        row = self.get_subscription(guild_id)
        now = utc_now_iso()
        if row is None:
            self.execute(
                """
                INSERT INTO guild_subscriptions (
                    guild_id, owner_id, plan_name, status, expires_at, max_tickets,
                    max_giveaways, casino_enabled, economy_enabled, premium_features_enabled,
                    locked, notes, created_at, updated_at
                )
                VALUES (?, 0, 'inactive', 'inactive', NULL, 0, 0, 0, 0, 0, 0, ?, ?, ?)
                """,
                (guild_id, notes, now, now),
            )
        else:
            self.execute(
                """
                UPDATE guild_subscriptions
                SET status = 'inactive',
                    casino_enabled = 0,
                    economy_enabled = 0,
                    premium_features_enabled = 0,
                    notes = COALESCE(?, notes),
                    updated_at = ?
                WHERE guild_id = ?
                """,
                (notes, now, guild_id),
            )

    def renew_subscription(self, guild_id: int, days: int) -> bool:
        row = self.get_subscription(guild_id)
        if row is None:
            return False
        current = self._parse_datetime(row["expires_at"]) or datetime.now(timezone.utc)
        base = max(current, datetime.now(timezone.utc))
        expires_at = (base + timedelta(days=max(days, 1))).isoformat()
        self.execute(
            """
            UPDATE guild_subscriptions
            SET status = 'active',
                expires_at = ?,
                locked = 0,
                casino_enabled = 1,
                economy_enabled = 1,
                premium_features_enabled = 1,
                updated_at = ?
            WHERE guild_id = ?
            """,
            (expires_at, utc_now_iso(), guild_id),
        )
        return True

    def set_subscription_lock(self, guild_id: int, locked: bool, reason: str | None = None) -> None:
        row = self.get_subscription(guild_id)
        now = utc_now_iso()
        if row is None:
            self.deactivate_subscription(guild_id, reason)
        self.execute(
            """
            UPDATE guild_subscriptions
            SET locked = ?, notes = COALESCE(?, notes), updated_at = ?
            WHERE guild_id = ?
            """,
            (1 if locked else 0, reason, now, guild_id),
        )

    def list_subscriptions(self) -> list[sqlite3.Row]:
        return self.fetchall(
            """
            SELECT *
            FROM guild_subscriptions
            ORDER BY status DESC, expires_at ASC
            """
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    def is_subscription_active(self, guild_id: int) -> bool:
        row = self.get_subscription(guild_id)
        if row is None or row["status"] != "active" or row["locked"]:
            return False
        expires_at = self._parse_datetime(row["expires_at"])
        return bool(expires_at and expires_at > datetime.now(timezone.utc))

    def feature_enabled(self, guild_id: int, feature: str) -> bool:
        if not self.is_subscription_active(guild_id):
            return False
        row = self.get_subscription(guild_id)
        if row is None:
            return False
        if feature == "casino":
            return bool(row["casino_enabled"])
        if feature == "economy":
            return bool(row["economy_enabled"])
        return bool(row["premium_features_enabled"])

    # Economy shop and inventory
    def get_shop_items(self, guild_id: int) -> list[sqlite3.Row]:
        return self.fetchall(
            """
            SELECT *
            FROM shop_items
            WHERE active = 1 AND guild_id IN (0, ?)
            ORDER BY guild_id ASC, price ASC
            """,
            (guild_id,),
        )

    def get_shop_item(self, guild_id: int, item_key: str) -> sqlite3.Row | None:
        return self.fetchone(
            """
            SELECT *
            FROM shop_items
            WHERE active = 1 AND key = ? AND guild_id IN (0, ?)
            ORDER BY guild_id DESC
            LIMIT 1
            """,
            (item_key, guild_id),
        )

    def add_inventory_item(self, guild_id: int, user_id: int, item_key: str, quantity: int = 1) -> None:
        self.ensure_user(guild_id, user_id)
        self.execute(
            """
            INSERT INTO inventories (guild_id, user_id, item_key, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, item_key) DO UPDATE SET
                quantity = quantity + excluded.quantity
            """,
            (guild_id, user_id, item_key, quantity),
        )

    def get_inventory(self, guild_id: int, user_id: int) -> list[sqlite3.Row]:
        self.ensure_user(guild_id, user_id)
        return self.fetchall(
            """
            SELECT i.*, s.name, s.description
            FROM inventories i
            LEFT JOIN shop_items s ON s.key = i.item_key AND s.guild_id IN (0, i.guild_id)
            WHERE i.guild_id = ? AND i.user_id = ? AND i.quantity > 0
            GROUP BY i.item_key
            ORDER BY i.item_key
            """,
            (guild_id, user_id),
        )

    def consume_inventory_item(self, guild_id: int, user_id: int, item_key: str) -> bool:
        with self._lock, self.connection:
            row = self.connection.execute(
                """
                SELECT quantity
                FROM inventories
                WHERE guild_id = ? AND user_id = ? AND item_key = ?
                """,
                (guild_id, user_id, item_key),
            ).fetchone()
            if row is None or row["quantity"] <= 0:
                return False
            self.connection.execute(
                """
                UPDATE inventories
                SET quantity = quantity - 1
                WHERE guild_id = ? AND user_id = ? AND item_key = ?
                """,
                (guild_id, user_id, item_key),
            )
            return True

    def buy_item(self, guild_id: int, user_id: int, item_key: str) -> tuple[bool, str]:
        item = self.get_shop_item(guild_id, item_key)
        if item is None:
            return False, "Item nao encontrado."
        with self._lock, self.connection:
            self.ensure_user(guild_id, user_id)
            row = self.connection.execute(
                "SELECT wallet FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            if row is None or row["wallet"] < item["price"]:
                return False, "Saldo insuficiente."
            self.connection.execute(
                "UPDATE users SET wallet = wallet - ?, total_lost = total_lost + ? WHERE guild_id = ? AND user_id = ?",
                (item["price"], item["price"], guild_id, user_id),
            )
            self.connection.execute(
                """
                INSERT INTO inventories (guild_id, user_id, item_key, quantity)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(guild_id, user_id, item_key) DO UPDATE SET quantity = quantity + 1
                """,
                (guild_id, user_id, item_key),
            )
            return True, item["name"]

    # Tickets
    def create_ticket(self, guild_id: int, owner_id: int, channel_id: int | None, reason: str | None) -> int:
        self.ensure_guild(guild_id)
        now = utc_now_iso()
        with self._lock, self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO tickets (guild_id, channel_id, owner_id, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (guild_id, channel_id, owner_id, reason, now),
            )
            return int(cursor.lastrowid)

    def get_open_ticket_for_user(self, guild_id: int, owner_id: int) -> sqlite3.Row | None:
        return self.fetchone(
            "SELECT * FROM tickets WHERE guild_id = ? AND owner_id = ? AND status = 'open' LIMIT 1",
            (guild_id, owner_id),
        )

    def get_ticket_by_channel(self, guild_id: int, channel_id: int) -> sqlite3.Row | None:
        return self.fetchone(
            "SELECT * FROM tickets WHERE guild_id = ? AND channel_id = ? ORDER BY id DESC LIMIT 1",
            (guild_id, channel_id),
        )

    def close_ticket(self, ticket_id: int, closed_by: int, transcript: str | None = None) -> None:
        now = utc_now_iso()
        with self._lock, self.connection:
            row = self.connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row is None:
                return
            self.connection.execute(
                "UPDATE tickets SET status = 'closed', closed_at = ?, closed_by = ? WHERE id = ?",
                (now, closed_by, ticket_id),
            )
            if transcript is not None:
                self.connection.execute(
                    """
                    INSERT INTO ticket_transcripts (ticket_id, guild_id, channel_id, content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (ticket_id, row["guild_id"], row["channel_id"], transcript, now),
                )

    def claim_ticket(self, guild_id: int, channel_id: int, user_id: int) -> bool:
        self.execute(
            "UPDATE tickets SET claimed_by = ? WHERE guild_id = ? AND channel_id = ? AND status = 'open'",
            (user_id, guild_id, channel_id),
        )
        return True

    # Moderation warnings
    def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
        with self._lock, self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, moderator_id, reason, utc_now_iso()),
            )
            return int(cursor.lastrowid)

    def get_warnings(self, guild_id: int, user_id: int) -> list[sqlite3.Row]:
        return self.fetchall(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
            (guild_id, user_id),
        )

    def clear_warnings(self, guild_id: int, user_id: int) -> int:
        with self._lock, self.connection:
            rows = self.connection.execute(
                "SELECT COUNT(*) AS total FROM warnings WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            self.connection.execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            return int(rows["total"] if rows else 0)
