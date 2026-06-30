"""
Shared Vercel webhook logic.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from aiogram.types import Update

from bot import create_bot, get_dispatcher
from config import WEBHOOK_SECRET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

_webhook_registered = False
_webhook_lock = asyncio.Lock()

GET_PATHS = {"/", "/api", "/api/", "/api/health", "/api/health/", "/health"}
POST_PATHS = {"/", "/api", "/api/", "/api/webhook", "/api/webhook/", "/webhook"}


async def ensure_webhook() -> None:
    """Optional — only if you want auto re-register on cold start."""
    global _webhook_registered
    async with _webhook_lock:
        if _webhook_registered:
            return
        from bot import setup_webhook
        async with create_bot() as bot:
            await setup_webhook(bot)
        _webhook_registered = True


def health_response() -> Dict[str, str]:
    return {"status": "ok"}


def _normalize_path(path: str) -> str:
    return path.split("?", 1)[0].rstrip("/") or "/"


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
        dp = await get_dispatcher()
        payload = json.loads(body.decode("utf-8"))

        async with create_bot() as bot:
            update = Update.model_validate(payload, context={"bot": bot})
            await dp.feed_update(bot, update)
    except Exception:
        log.exception("Failed to process Telegram update.")
        return 500, {"error": "internal server error"}

    return 200, {"ok": True}


def handle_http(method: str, path: str, body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    """Sync entry for Vercel BaseHTTPRequestHandler."""
    norm = _normalize_path(path)
    log.info("%s %s (normalized: %s)", method, path, norm)

    if method == "GET":
        # Accept /api/health with or without trailing slash
        if norm in GET_PATHS or norm == "/api/health":
            return 200, health_response()
        return 404, {"error": "not found"}

    if method == "POST":
        if norm in POST_PATHS or norm == "/api":
            return asyncio.run(process_webhook(body, headers))
        return 404, {"error": "not found"}

    return 405, {"error": "method not allowed"}
