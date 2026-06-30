"""
Single Vercel entry point for all /api/* traffic.

Vercel forwards the FULL path (e.g. /api/health) to FastAPI,
so every route must be registered with the complete path.
"""
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse

from vercel_app import health_response, process_webhook

app = FastAPI()

# Every path Vercel / Telegram may hit
_GET_PATHS = ("/", "/api", "/api/", "/api/health", "/api/webhook", "/health")
_POST_PATHS = ("/", "/api", "/api/", "/api/webhook", "/webhook")


def _register(method: str, paths: tuple, handler) -> None:
    for path in paths:
        app.add_api_route(path, handler, methods=[method])


async def health() -> dict:
    return health_response()


async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> Response:
    headers = dict(request.headers)
    if x_telegram_bot_api_secret_token:
        headers["x-telegram-bot-api-secret-token"] = x_telegram_bot_api_secret_token
    status, body = await process_webhook(await request.body(), headers)
    return JSONResponse(content=body, status_code=status)


_register("GET", _GET_PATHS, health)
_register("POST", _POST_PATHS, webhook)
