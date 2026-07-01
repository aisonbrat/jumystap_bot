"""
Async-safe reader/writer for bot settings stored in Redis.
"""
from database import db_get_settings, db_save_settings

# Re-export defaults for tests / scripts that need them
from database import SETTINGS_DEFAULTS as _DEFAULTS  # noqa: F401


async def get() -> dict:
    """Return a merged copy of defaults + persisted settings."""
    return await db_get_settings()


async def save(**fields) -> None:
    """Persist one or more key=value pairs, keeping everything else intact."""
    await db_save_settings(**fields)
