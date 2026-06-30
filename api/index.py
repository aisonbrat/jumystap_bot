"""
Vercel serverless entry point — receives Telegram webhook POST requests.

Webhook URL:  https://<your-production-domain>/api
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, Header, Request, Response
from aiogram.types import Update

from bot import create_bot, get_dispatcher, setup_webhook
from config import WEBHOOK_SECRET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

app = FastAPI()

_webhook_registered = False
_webhook_lock = asyncio.Lock()


async def _ensure_webhook() -> None:
    """Register webhook once per warm instance (lifespan is unreliable on Vercel)."""
    global _webhook_registered
    async with _webhook_lock:
        if _webhook_registered:
            return
        async with create_bot() as bot:
            await setup_webhook(bot)
        _webhook_registered = True


async def _handle_telegram_update(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str],
) -> Response:
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        log.warning("Rejected webhook: invalid secret token.")
        return Response(status_code=403)

    try:
        await _ensure_webhook()
        dp = await get_dispatcher()
        body = await request.json()

        # Fresh Bot per request — closes aiohttp session and avoids
        # "Unclosed connector" errors when Vercel freezes the function.
        async with create_bot() as bot:
            update = Update.model_validate(body, context={"bot": bot})
            await dp.feed_update(bot, update)
    except Exception:
        log.exception("Failed to process Telegram update.")
        return Response(status_code=500)

    return Response(status_code=200)


@app.get("/")
@app.get("/health")
@app.get("/webhook")
@app.get("/api/webhook")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/")
@app.post("/webhook")
@app.post("/api/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> Response:
    return await _handle_telegram_update(request, x_telegram_bot_api_secret_token)
