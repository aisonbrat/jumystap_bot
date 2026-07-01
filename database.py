"""
Persistent storage via Redis (Upstash on Vercel, optional locally).

Free tier: https://upstash.com — create a database, copy the Redis URL (TLS).
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from config import REDIS_URL
from redis_client import redis_connection_kwargs, redis_from_url_kwargs

log = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None

AUTH_SET_KEY = "bot:authenticated_users"
SETTINGS_KEY = "bot:settings"

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


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        if not REDIS_URL:
            raise RuntimeError(
                "REDIS_URL is not set. "
                "Create a free Upstash Redis database and add the URL to Vercel env vars."
            )
        _redis = aioredis.from_url(
            REDIS_URL,
            **redis_from_url_kwargs(decode_responses=True),
        )
        log.info("Redis connection ready.")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is None:
        return
    try:
        await _redis.aclose()
    except Exception:
        log.exception("Error closing Redis connection.")
    finally:
        _redis = None


# ── Auth ──────────────────────────────────────────────────────────────────────

async def db_authenticate(user_id: int) -> None:
    r = await get_redis()
    await r.sadd(AUTH_SET_KEY, str(user_id))


async def db_is_authenticated(user_id: int) -> bool:
    r = await get_redis()
    return bool(await r.sismember(AUTH_SET_KEY, str(user_id)))


async def db_revoke_authentication(user_id: int) -> None:
    r = await get_redis()
    await r.srem(AUTH_SET_KEY, str(user_id))


# ── Settings ──────────────────────────────────────────────────────────────────

async def db_get_settings() -> Dict[str, str]:
    r = await get_redis()
    raw = await r.get(SETTINGS_KEY)
    if not raw:
        return dict(SETTINGS_DEFAULTS)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return dict(SETTINGS_DEFAULTS)
    return {**SETTINGS_DEFAULTS, **data}


async def db_save_settings(**fields: Any) -> None:
    allowed = set(SETTINGS_DEFAULTS)
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    current = await db_get_settings()
    current.update(updates)
    r = await get_redis()
    await r.set(SETTINGS_KEY, json.dumps(current, ensure_ascii=False))


async def db_seed_settings_from_json(path: str = "settings.json") -> None:
    """Import settings.json into Redis on first run."""
    r = await get_redis()
    if await r.exists(SETTINGS_KEY):
        return
    p = Path(path)
    if not p.exists():
        await db_save_settings(**SETTINGS_DEFAULTS)
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        await db_save_settings(**SETTINGS_DEFAULTS)
        return
    await db_save_settings(**data)
    log.info("Seeded Redis settings from %s", path)
