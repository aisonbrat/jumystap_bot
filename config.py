import logging
import os

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── Required ─────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")

# Supabase PostgreSQL connection pooler URI (port 6543, ?pgbouncer=true).
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# ── Auth ─────────────────────────────────────────────────────────────────────
BOT_PASSWORD: str = os.environ.get("BOT_PASSWORD", "Gorifa10")

# ── Webhook (Vercel / production) ────────────────────────────────────────────
WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")

# Stable production URL, e.g. https://jumystapbot.vercel.app
WEBHOOK_BASE_URL: str = os.environ.get("WEBHOOK_BASE_URL", "")


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
