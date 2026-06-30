"""GET/POST https://<domain>/api/webhook — alias for Telegram webhook."""
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


@app.get("/")
async def health() -> dict:
    return health_response()


@app.post("/")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> Response:
    headers = dict(request.headers)
    if x_telegram_bot_api_secret_token:
        headers["x-telegram-bot-api-secret-token"] = x_telegram_bot_api_secret_token
    status, body = await process_webhook(await request.body(), headers)
    return JSONResponse(content=body, status_code=status)
