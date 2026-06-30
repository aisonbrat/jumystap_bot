"""
Vercel serverless entry point — receives Telegram webhook POST requests.

Webhook URL to register with Telegram:  https://<your-domain>/api
"""
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# Project root must be on sys.path so `bot`, `handlers`, etc. import cleanly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, Header, Request, Response
from aiogram.types import Update

from bot import create_bot_and_dispatcher, setup_webhook
from config import WEBHOOK_SECRET
from database import close_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

bot = None
dp = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global bot, dp
    bot, dp = await create_bot_and_dispatcher()
    await setup_webhook(bot)
    yield
    await bot.session.close()
    await close_pool()


app = FastAPI(lifespan=lifespan)


@app.get("/")
@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> Response:
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        log.warning("Rejected webhook: invalid secret token.")
        return Response(status_code=403)

    try:
        body = await request.json()
        update = Update.model_validate(body, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        log.exception("Failed to process Telegram update.")
        return Response(status_code=500)

    return Response(status_code=200)
