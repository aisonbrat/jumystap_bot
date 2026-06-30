import os

from dotenv import load_dotenv

load_dotenv()

# ── Required ─────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")

# Supabase PostgreSQL connection pooler URI (port 6543, ?pgbouncer=true).
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# ── Auth ─────────────────────────────────────────────────────────────────────
BOT_PASSWORD: str = os.environ.get("BOT_PASSWORD", "Gorifa10")

# ── Webhook (Vercel / production) ────────────────────────────────────────────
# Optional secret sent in X-Telegram-Bot-Api-Secret-Token header
WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")

# Override the public base URL (e.g. https://my-bot.vercel.app).
# When unset, VERCEL_URL is used automatically on Vercel.
WEBHOOK_BASE_URL: str = os.environ.get("WEBHOOK_BASE_URL", "")


def get_webhook_url() -> str:
    """Full Telegram webhook URL (POST target for updates)."""
    # Always prefer the stable production URL — VERCEL_URL changes on every deploy.
    base = WEBHOOK_BASE_URL.rstrip("/") if WEBHOOK_BASE_URL else ""
    if not base:
        prod = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "")
        if prod:
            base = f"https://{prod}"
    if not base:
        vercel_url = os.environ.get("VERCEL_URL", "")
        if vercel_url:
            base = f"https://{vercel_url}"
    if not base:
        host = os.environ.get("WEBHOOK_HOST", "localhost")
        port = os.environ.get("PORT", "8080")
        base = f"http://{host}:{port}"
    return f"{base.rstrip('/')}/api"
