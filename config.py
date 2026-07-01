import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


def _clean_env(key: str, default: str = "") -> str:
    value = os.environ.get(key, default).strip().strip('"').strip("'")
    return value


# ── Required ─────────────────────────────────────────────────────────────────
BOT_TOKEN: str = _clean_env("BOT_TOKEN")

# Upstash REST API (HTTPS) — Upstash console → your DB → REST API tab
# NOT the rediss:// TCP URL (that breaks on Vercel serverless).
UPSTASH_REDIS_REST_URL: str = (
    _clean_env("UPSTASH_REDIS_REST_URL")
    or _clean_env("KV_REST_API_URL")  # Vercel + Upstash integration
)
UPSTASH_REDIS_REST_TOKEN: str = (
    _clean_env("UPSTASH_REDIS_REST_TOKEN")
    or _clean_env("KV_REST_API_TOKEN")
)

# ── Auth ─────────────────────────────────────────────────────────────────────
BOT_PASSWORD: str = _clean_env("BOT_PASSWORD", "Gorifa10")

# ── Webhook (Vercel / production) ────────────────────────────────────────────
WEBHOOK_SECRET: str = _clean_env("WEBHOOK_SECRET")
WEBHOOK_BASE_URL: str = _clean_env("WEBHOOK_BASE_URL")


def upstash_configured() -> bool:
    return upstash_config_error() is None


def upstash_config_error() -> Optional[str]:
    url = UPSTASH_REDIS_REST_URL
    token = UPSTASH_REDIS_REST_TOKEN

    if _clean_env("REDIS_URL"):
        return (
            "REDIS_URL is no longer used. Remove it from Vercel and set "
            "UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN from the REST API tab."
        )
    if not url or not token:
        return (
            "Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN "
            "(Upstash console → REST API tab)."
        )
    if url.startswith("rediss://") or url.startswith("redis://"):
        return (
            "UPSTASH_REDIS_REST_URL must be the HTTPS REST URL, not rediss://. "
            "Copy it from Upstash → REST API tab."
        )
    if not url.startswith("https://"):
        return "UPSTASH_REDIS_REST_URL must start with https://"
    return None


def get_webhook_url() -> str:
    """Full Telegram webhook URL (POST target for updates)."""
    base = WEBHOOK_BASE_URL.rstrip("/") if WEBHOOK_BASE_URL else ""
    if not base:
        prod = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "")
        if prod:
            base = f"https://{prod}"
    if not base:
        vercel_url = os.environ.get("VERCEL_URL", "")
        if vercel_url:
            if os.environ.get("VERCEL") and not WEBHOOK_BASE_URL:
                log.warning(
                    "WEBHOOK_BASE_URL not set — using preview URL %s. "
                    "Set WEBHOOK_BASE_URL=https://jumystapbot.vercel.app",
                    vercel_url,
                )
            base = f"https://{vercel_url}"
    if not base:
        host = os.environ.get("WEBHOOK_HOST", "localhost")
        port = os.environ.get("PORT", "8080")
        base = f"http://{host}:{port}"
    return f"{base.rstrip('/')}/api"
