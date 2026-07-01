"""
Shared Vercel webhook logic.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from aiogram.types import Update

from bot import create_bot, get_dispatcher, reset_runtime
from config import WEBHOOK_SECRET, upstash_config_error
from database import ping_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

GET_PATHS = {"/", "/api", "/api/", "/api/health", "/api/health/", "/health"}
POST_PATHS = {"/", "/api", "/api/", "/api/webhook", "/api/webhook/", "/webhook"}


async def health_response() -> Dict[str, Any]:
    body: Dict[str, Any] = {"status": "ok"}
    config_error = upstash_config_error()
    if config_error:
        body["status"] = "misconfigured"
        body["redis"] = config_error
        return body
    try:
        body["redis"] = "ok" if await ping_redis() else "fail"
    except Exception as exc:
        log.exception("Redis health check failed.")
        body["status"] = "error"
        body["redis"] = f"error: {exc}"
    return body


def _normalize_path(path: str) -> str:
    return path.split("?", 1)[0].rstrip("/") or "/"


def _get_header(headers: Dict[str, str], name: str) -> Optional[str]:
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


async def _safe_reset_runtime() -> None:
    try:
        await reset_runtime()
    except Exception:
        log.exception("Failed to reset runtime after request.")


async def process_webhook(
    body: bytes,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, Any]]:
    headers = headers or {}
    secret = _get_header(headers, "X-Telegram-Bot-Api-Secret-Token")

    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        log.warning("Rejected webhook: invalid secret token.")
        return 403, {"error": "forbidden"}

    status, response = 200, {"ok": True}
    try:
        dp = await get_dispatcher()
        payload = json.loads(body.decode("utf-8"))

        async with create_bot() as bot:
            update = Update.model_validate(payload, context={"bot": bot})
            await dp.feed_update(bot, update)
    except Exception as exc:
        log.exception("Failed to process Telegram update: %s", exc)
        status, response = 500, {"error": "internal server error"}
    finally:
        await _safe_reset_runtime()

    return status, response


def handle_http(method: str, path: str, body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    norm = _normalize_path(path)
    log.info("%s %s (normalized: %s)", method, path, norm)

    if method == "GET":
        if norm in GET_PATHS:
            return 200, asyncio.run(health_response())
        return 404, {"error": "not found"}

    if method == "POST":
        if norm in POST_PATHS:
            return asyncio.run(process_webhook(body, headers))
        return 404, {"error": "not found"}

    return 405, {"error": "method not allowed"}
