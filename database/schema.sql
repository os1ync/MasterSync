PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    welcome_channel_id INTEGER,
    welcome_enabled INTEGER NOT NULL DEFAULT 1,
    welcome_message TEXT DEFAULT 'Bem-Vindo(a) {mention}.\nVoce e o membro numero #{member_number} do servidor.',
    welcome_embed_enabled INTEGER NOT NULL DEFAULT 0,
    welcome_rules_url TEXT,
    leave_channel_id INTEGER,
    leave_enabled INTEGER NOT NULL DEFAULT 0,
    leave_message TEXT DEFAULT '{user} saiu do servidor.',
    logs_channel_id INTEGER,
    logs_enabled INTEGER NOT NULL DEFAULT 1,
    casino_enabled INTEGER NOT NULL DEFAULT 1,
    economy_enabled INTEGER NOT NULL DEFAULT 1,
    tickets_enabled INTEGER NOT NULL DEFAULT 1,
    levels_enabled INTEGER NOT NULL DEFAULT 1,
    giveaways_enabled INTEGER NOT NULL DEFAULT 1,
    automod_enabled INTEGER NOT NULL DEFAULT 0,
    antiraid_enabled INTEGER NOT NULL DEFAULT 0,
    autorole_enabled INTEGER NOT NULL DEFAULT 0,
    autorole_delay INTEGER NOT NULL DEFAULT 0,
    ticket_category_id INTEGER,
    ticket_support_role_id INTEGER,
    ticket_logs_channel_id INTEGER,
    ticket_limit_per_user INTEGER NOT NULL DEFAULT 1,
    casino_min_bet INTEGER NOT NULL DEFAULT 10,
    casino_max_bet INTEGER NOT NULL DEFAULT 50000,
    casino_daily_loss_limit INTEGER NOT NULL DEFAULT 0,
    casino_house_edge_percent REAL NOT NULL DEFAULT 0,
    prefix TEXT NOT NULL DEFAULT '/'
);

CREATE TABLE IF NOT EXISTS guild_configs (
    guild_id TEXT PRIMARY KEY,
    guild_name TEXT,
    welcome_enabled INTEGER NOT NULL DEFAULT 1,
    welcome_channel_id TEXT,
    welcome_message TEXT NOT NULL DEFAULT 'Bem-Vindo(a) {user_mention}.\nVoce e o membro numero #{member_count} do servidor.',
    autorole_enabled INTEGER NOT NULL DEFAULT 0,
    autorole_role_id TEXT,
    logs_enabled INTEGER NOT NULL DEFAULT 1,
    logs_channel_id TEXT,
    log_member_join INTEGER NOT NULL DEFAULT 1,
    log_member_leave INTEGER NOT NULL DEFAULT 1,
    log_message_delete INTEGER NOT NULL DEFAULT 1,
    log_message_edit INTEGER NOT NULL DEFAULT 1,
    log_moderation INTEGER NOT NULL DEFAULT 1,
    tickets_enabled INTEGER NOT NULL DEFAULT 1,
    tickets_category_id TEXT,
    tickets_panel_message TEXT NOT NULL DEFAULT 'Clique no botao para abrir um ticket privado com a equipe.',
    tickets_support_role_id TEXT,
    automod_enabled INTEGER NOT NULL DEFAULT 0,
    economy_enabled INTEGER NOT NULL DEFAULT 1,
    casino_enabled INTEGER NOT NULL DEFAULT 1,
    giveaways_enabled INTEGER NOT NULL DEFAULT 1,
    levels_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dashboard_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    username TEXT NOT NULL,
    discriminator TEXT,
    avatar TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dashboard_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    guild_id TEXT,
    action TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guild_subscriptions (
    guild_id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    plan_name TEXT NOT NULL DEFAULT 'inactive',
    status TEXT NOT NULL DEFAULT 'inactive',
    expires_at TEXT,
    max_tickets INTEGER NOT NULL DEFAULT 0,
    max_giveaways INTEGER NOT NULL DEFAULT 0,
    casino_enabled INTEGER NOT NULL DEFAULT 0,
    economy_enabled INTEGER NOT NULL DEFAULT 0,
    premium_features_enabled INTEGER NOT NULL DEFAULT 0,
    locked INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    wallet INTEGER NOT NULL DEFAULT 0,
    bank INTEGER NOT NULL DEFAULT 0,
    total_earned INTEGER NOT NULL DEFAULT 0,
    total_lost INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_daily TEXT,
    last_work TEXT,
    work_boost_until TEXT,
    casino_multiplier_until TEXT,
    robbery_protection_until TEXT,
    PRIMARY KEY (user_id, guild_id),
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS casino_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    game TEXT NOT NULL,
    bet INTEGER NOT NULL,
    result TEXT NOT NULL,
    profit INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER,
    owner_id INTEGER NOT NULL,
    claimed_by INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    reason TEXT,
    blocked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    closed_by INTEGER
);

CREATE TABLE IF NOT EXISTS ticket_transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS levels (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 0,
    last_xp TEXT,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS level_roles (
    guild_id INTEGER NOT NULL,
    level INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, level)
);

CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER,
    prize TEXT NOT NULL,
    winners INTEGER NOT NULL DEFAULT 1,
    ends_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS giveaway_entries (
    giveaway_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (giveaway_id, user_id)
);

CREATE TABLE IF NOT EXISTS autoroles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'join',
    label TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automod_settings (
    guild_id INTEGER PRIMARY KEY,
    anti_link INTEGER NOT NULL DEFAULT 0,
    anti_spam INTEGER NOT NULL DEFAULT 0,
    anti_caps INTEGER NOT NULL DEFAULT 0,
    anti_mentions INTEGER NOT NULL DEFAULT 0,
    banned_words TEXT,
    punishment TEXT NOT NULL DEFAULT 'delete',
    whitelist_channels TEXT,
    whitelist_roles TEXT
);

CREATE TABLE IF NOT EXISTS antiraid_settings (
    guild_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    join_limit INTEGER NOT NULL DEFAULT 6,
    window_seconds INTEGER NOT NULL DEFAULT 20,
    action TEXT NOT NULL DEFAULT 'lockdown',
    lockdown_until TEXT
);

CREATE TABLE IF NOT EXISTS shop_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL DEFAULT 0,
    key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(guild_id, key)
);

CREATE TABLE IF NOT EXISTS inventories (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_users_guild_ranking ON users (guild_id, wallet, bank);
CREATE INDEX IF NOT EXISTS idx_casino_history_user ON casino_history (guild_id, user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_guild_owner ON tickets (guild_id, owner_id, status);
CREATE INDEX IF NOT EXISTS idx_warnings_user ON warnings (guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_giveaways_status ON giveaways (guild_id, status, ends_at);
