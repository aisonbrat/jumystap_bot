"""
Upstash Redis via HTTPS REST API (works on Vercel — no TCP/SSL issues).

In Upstash console → your database → REST API tab, copy:
  UPSTASH_REDIS_REST_URL
  UPSTASH_REDIS_REST_TOKEN
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set

from upstash_redis.asyncio import Redis

from config import UPSTASH_REDIS_REST_TOKEN, UPSTASH_REDIS_REST_URL, upstash_config_error

log = logging.getLogger(__name__)

_redis: Optional[Redis] = None
_auth_users_cache: Optional[frozenset] = None
_settings_cache: Optional[Dict[str, str]] = None

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


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        err = upstash_config_error()
        if err:
            raise RuntimeError(err)
        _redis = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)
        log.info("Upstash Redis REST client ready.")
    return _redis


async def close_redis() -> None:
    global _redis
    _redis = None


async def ping_redis() -> bool:
    r = get_redis()
    result = await r.ping()
    return result == "PONG" or result is True


# ── Auth (stored as JSON list — REST has no native sets in all plans) ────────

def _invalidate_auth_cache() -> None:
    global _auth_users_cache
    _auth_users_cache = None


def _invalidate_settings_cache() -> None:
    global _settings_cache
    _settings_cache = None


async def _get_auth_users() -> set:
    global _auth_users_cache
    if _auth_users_cache is not None:
        return set(_auth_users_cache)

    r = get_redis()
    raw = await r.get(AUTH_SET_KEY)
    if not raw:
        users: Set[str] = set()
    else:
        try:
            users = set(json.loads(raw))
        except json.JSONDecodeError:
            users = set()

    _auth_users_cache = frozenset(users)
    return set(users)


async def _save_auth_users(users: set) -> None:
    r = get_redis()
    await r.set(AUTH_SET_KEY, json.dumps(list(users)))
    _auth_users_cache = frozenset(users)


async def db_authenticate(user_id: int) -> None:
    users = await _get_auth_users()
    users.add(str(user_id))
    await _save_auth_users(users)


async def db_is_authenticated(user_id: int) -> bool:
    users = await _get_auth_users()
    return str(user_id) in users


async def db_revoke_authentication(user_id: int) -> None:
    users = await _get_auth_users()
    users.discard(str(user_id))
    await _save_auth_users(users)


# ── Settings ──────────────────────────────────────────────────────────────────

async def db_get_settings() -> Dict[str, str]:
    global _settings_cache
    if _settings_cache is not None:
        return dict(_settings_cache)

    r = get_redis()
    raw = await r.get(SETTINGS_KEY)
    if not raw:
        merged = dict(SETTINGS_DEFAULTS)
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        merged = {**SETTINGS_DEFAULTS, **data}

    _settings_cache = merged
    return dict(merged)


async def db_save_settings(**fields: Any) -> None:
    allowed = set(SETTINGS_DEFAULTS)
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    current = await db_get_settings()
    current.update(updates)
    r = get_redis()
    await r.set(SETTINGS_KEY, json.dumps(current, ensure_ascii=False))
    global _settings_cache
    _settings_cache = dict(current)


async def db_seed_settings_from_json(path: str = "settings.json") -> None:
    r = get_redis()
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
    log.info("Seeded settings from %s", path)
