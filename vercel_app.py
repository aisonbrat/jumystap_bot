"""
Shared Vercel webhook logic.
"""
import asyncio
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple, TypeVar

from aiogram.types import Update

from bot import create_bot, get_dispatcher
from config import WEBHOOK_SECRET, upstash_config_error
from database import ping_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

GET_PATHS = {"/", "/api", "/api/", "/api/health", "/api/health/", "/health"}
POST_PATHS = {"/", "/api", "/api/", "/api/webhook", "/api/webhook/", "/webhook"}

T = TypeVar("T")

# One event loop per warm Vercel instance — asyncio.run() per request was breaking
# the shared dispatcher/storage (bound to a closed loop) → hangs → 500 → Telegram
# retries minutes later.
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_init = threading.Lock()
_request_lock = threading.Lock()


def _get_event_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _loop_init:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            log.info("Created persistent event loop for warm instance.")
        return _loop


def run_async(coro) -> T:
    """Run coroutine on the instance event loop (serialized per warm instance)."""
    loop = _get_event_loop()
    with _request_lock:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


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


async def process_webhook(
    body: bytes,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, Any]]:
    headers = headers or {}
    secret = _get_header(headers, "X-Telegram-Bot-Api-Secret-Token")

    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        log.warning("Rejected webhook: invalid secret token.")
        return 403, {"error": "forbidden"}

    started = time.monotonic()
    status, response = 200, {"ok": True}
    try:
        dp = await get_dispatcher()
        payload = json.loads(body.decode("utf-8"))
        update_id = payload.get("update_id", "?")

        async with create_bot() as bot:
            update = Update.model_validate(payload, context={"bot": bot})
            await dp.feed_update(bot, update)

        elapsed = time.monotonic() - started
        log.info("Update %s handled in %.2fs", update_id, elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - started
        log.exception("Failed to process update after %.2fs: %s", elapsed, exc)
        status, response = 500, {"error": "internal server error"}

    return status, response


def handle_http(method: str, path: str, body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    norm = _normalize_path(path)
    log.info("%s %s (normalized: %s)", method, path, norm)

    if method == "GET":
        if norm in GET_PATHS:
            return 200, run_async(health_response())
        return 404, {"error": "not found"}

    if method == "POST":
        if norm in POST_PATHS:
            return run_async(process_webhook(body, headers))
        return 404, {"error": "not found"}

    return 405, {"error": "method not allowed"}
