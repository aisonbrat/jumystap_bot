"""
Async PostgreSQL access (Supabase).

Set DATABASE_URL to the Supabase *connection pooler* URI (port 6543, mode=transaction)
for serverless — Settings → Database → Connection string → URI → "Transaction pooler".
"""
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

import asyncpg

from config import DATABASE_URL

log = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS fsm_states (
    storage_key TEXT PRIMARY KEY,
    state       TEXT,
    data        JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fsm_states_updated_at ON fsm_states (updated_at);

CREATE TABLE IF NOT EXISTS authenticated_users (
    user_id           BIGINT PRIMARY KEY,
    authenticated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bot_settings (
    id                    SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    channel_id            TEXT NOT NULL DEFAULT '',
    footer                TEXT NOT NULL DEFAULT '',
    permanent_button_text TEXT NOT NULL DEFAULT '',
    permanent_button_url  TEXT NOT NULL DEFAULT '',
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO bot_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
"""


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. "
                "Add your Supabase connection pooler URI to .env / Vercel env vars."
            )
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=30,
            statement_cache_size=0,  # required for Supabase transaction pooler
        )
        await init_schema(_pool)
        log.info("PostgreSQL connection pool ready.")
    return _pool


async def init_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(_INIT_SQL)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("PostgreSQL connection pool closed.")


# ── Auth ──────────────────────────────────────────────────────────────────────

async def db_authenticate(user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO authenticated_users (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO UPDATE
                SET authenticated_at = NOW()
            """,
            user_id,
        )


async def db_is_authenticated(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        found = await conn.fetchval(
            "SELECT 1 FROM authenticated_users WHERE user_id = $1",
            user_id,
        )
    return found is not None


async def db_revoke_authentication(user_id: int) -> None:
    """Optional helper — remove a user from the authenticated list."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM authenticated_users WHERE user_id = $1",
            user_id,
        )


# ── Settings ──────────────────────────────────────────────────────────────────

_settings_cache: Optional[Tuple[Dict[str, str], float]] = None
_SETTINGS_TTL_SEC = 60.0

SETTINGS_DEFAULTS: Dict[str, str] = {
    "channel_id": "",
    "footer": (
        "✨✨\n\n"
        "🔎 JumysTap – бізден жұмыс тап\n"
        "#JumysTap\n"
        "https://t.me/jumystap1"
    ),
    "permanent_button_text": "JumysTap-қа ВАКАНСИЯ ЖАРИЯЛАУ",
    "permanent_button_url": "https://t.me/zhaksytayev",
}


async def db_get_settings() -> Dict[str, str]:
    global _settings_cache
    now = time.monotonic()
    if _settings_cache and now - _settings_cache[1] < _SETTINGS_TTL_SEC:
        return dict(_settings_cache[0])

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT channel_id, footer, permanent_button_text, permanent_button_url
            FROM bot_settings
            WHERE id = 1
            """,
        )
    if row is None:
        result = dict(SETTINGS_DEFAULTS)
    else:
        result = {**SETTINGS_DEFAULTS, **dict(row)}

    _settings_cache = (result, now)
    return dict(result)


async def db_save_settings(**fields: Any) -> None:
    global _settings_cache

    allowed = set(SETTINGS_DEFAULTS)
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return

    _settings_cache = None

    pool = await get_pool()
    async with pool.acquire() as conn:
        current = await conn.fetchrow(
            "SELECT channel_id, footer, permanent_button_text, permanent_button_url "
            "FROM bot_settings WHERE id = 1",
        )
        merged = {**SETTINGS_DEFAULTS, **(dict(current) if current else {})}
        merged.update(updates)

        await conn.execute(
            """
            INSERT INTO bot_settings (
                id, channel_id, footer, permanent_button_text, permanent_button_url
            )
            VALUES (1, $1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET
                channel_id            = EXCLUDED.channel_id,
                footer                = EXCLUDED.footer,
                permanent_button_text = EXCLUDED.permanent_button_text,
                permanent_button_url  = EXCLUDED.permanent_button_url,
                updated_at            = NOW()
            """,
            merged["channel_id"],
            merged["footer"],
            merged["permanent_button_text"],
            merged["permanent_button_url"],
        )


async def db_seed_settings_from_json(path: str = "settings.json") -> None:
    """One-time import of local settings.json into the database."""
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        log.warning("Could not read %s for DB seed.", path)
        return

    current = await db_get_settings()
    if current.get("channel_id"):
        return

    await db_save_settings(**data)
    log.info("Seeded bot_settings from %s", path)
