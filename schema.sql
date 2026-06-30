-- Run once in Supabase SQL Editor (Dashboard → SQL → New query).
-- The bot also auto-creates these tables on first connect via database.init_schema().

-- ── FSM state (aiogram) ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fsm_states (
    storage_key TEXT PRIMARY KEY,
    state       TEXT,
    data        JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fsm_states_updated_at ON fsm_states (updated_at);

-- ── Authenticated Telegram users ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS authenticated_users (
    user_id           BIGINT PRIMARY KEY,
    authenticated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Bot settings (singleton row, id = 1) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_settings (
    id                    SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    channel_id            TEXT NOT NULL DEFAULT '',
    footer                TEXT NOT NULL DEFAULT '',
    permanent_button_text TEXT NOT NULL DEFAULT '',
    permanent_button_url  TEXT NOT NULL DEFAULT '',
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO bot_settings (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;
