"""
Shared Vercel webhook logic (not a serverless route — lives outside api/).
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from aiogram.types import Update

from bot import create_bot, get_dispatcher, setup_webhook
from config import WEBHOOK_SECRET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

_webhook_registered = False
_webhook_lock = asyncio.Lock()


async def ensure_webhook() -> None:
    global _webhook_registered
    async with _webhook_lock:
        if _webhook_registered:
            return
        async with create_bot() as bot:
            await setup_webhook(bot)
        _webhook_registered = True


def health_response() -> Dict[str, str]:
    return {"status": "ok"}


def _get_header(headers: Dict[str, str], name: str) -> Optional[str]:
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


async def process_webhook(
    body: bytes,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, Any]]:
    headers = headers or {}
    secret = _get_header(headers, "X-Telegram-Bot-Api-Secret-Token")

    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        log.warning("Rejected webhook: invalid secret token.")
        return 403, {"error": "forbidden"}

    try:
        await ensure_webhook()
        dp = await get_dispatcher()
        payload = json.loads(body.decode("utf-8"))

        async with create_bot() as bot:
            update = Update.model_validate(payload, context={"bot": bot})
            await dp.feed_update(bot, update)
    except Exception:
        log.exception("Failed to process Telegram update.")
        return 500, {"error": "internal server error"}

    return 200, {"ok": True}
