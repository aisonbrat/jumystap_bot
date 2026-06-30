"""
Bot factory, webhook setup, and local long-polling entry point.

Production (Vercel):  api/index.py uses get_dispatcher() + per-request Bot.
Local development:    python bot.py
"""
import asyncio
import logging
import os
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, Message

from auth import AuthMiddleware, authenticate, is_authenticated, logout
from config import BOT_PASSWORD, BOT_TOKEN, get_webhook_url
from database import close_pool, db_seed_settings_from_json, get_pool
from fsm_storage import PostgreSQLStorage
from handlers import post, settings_panel
from states import AuthFlow
from web import start_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

_dispatcher: Optional[Dispatcher] = None
_dispatcher_lock: Optional[asyncio.Lock] = None


def _get_dispatcher_lock() -> asyncio.Lock:
    global _dispatcher_lock
    if _dispatcher_lock is None:
        _dispatcher_lock = asyncio.Lock()
    return _dispatcher_lock


async def reset_runtime() -> None:
    """Tear down globals after each Vercel request (asyncio.run closes the loop)."""
    global _dispatcher, _dispatcher_lock
    _dispatcher = None
    _dispatcher_lock = None
    await close_pool()


# ── Bot commands ──────────────────────────────────────────────────────────────

async def _set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start",    description="Start / unlock the bot"),
        BotCommand(command="settings", description="Open settings"),
        BotCommand(command="cancel",   description="Cancel current action"),
        BotCommand(command="logout",   description="Sign out"),
    ])


# ── /start ────────────────────────────────────────────────────────────────────

async def _cmd_start(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else None

    if uid and await is_authenticated(uid):
        await state.clear()
        await message.answer(
            "👋 <b>JumysTap Bot</b>\n\n"
            "Send a job vacancy text — the bot will parse contacts and show a preview.\n\n"
            "/settings — bot settings\n"
            "/cancel   — cancel current action\n"
            "/logout   — sign out",
        )
        return

    await state.set_state(AuthFlow.waiting_password)
    await message.answer("🔐 <b>Enter the password to unlock the bot:</b>")


# ── Password entry ────────────────────────────────────────────────────────────

async def _check_password(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() == BOT_PASSWORD:
        await authenticate(message.from_user.id)
        await state.clear()
        log.info("User %d authenticated.", message.from_user.id)
        await message.answer(
            "✅ <b>Access granted!</b>\n\n"
            "👋 <b>JumysTap Bot</b>\n\n"
            "Send a job vacancy text — the bot will parse contacts and show a preview.\n\n"
            "/settings — bot settings\n"
            "/cancel   — cancel current action\n"
            "/logout   — sign out",
        )
    else:
        await message.answer("❌ Wrong password. Try again:")


# ── /logout ──────────────────────────────────────────────────────────────────

async def _cmd_logout(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else None
    if not uid:
        return

    if not await is_authenticated(uid):
        await message.answer("ℹ️ You are not logged in. Send /start to authenticate.")
        return

    await logout(uid)
    await state.clear()
    log.info("User %d logged out.", uid)
    await message.answer(
        "👋 <b>Logged out.</b>\n\nSend /start when you want to sign in again.",
    )


# ── Dispatcher wiring ────────────────────────────────────────────────────────

def _wire_dispatcher(dp: Dispatcher) -> None:
    dp.message.outer_middleware(AuthMiddleware())
    dp.callback_query.outer_middleware(AuthMiddleware())

    dp.message.register(_cmd_start, Command("start"))
    dp.message.register(_cmd_logout, Command("logout"))
    dp.message.register(_check_password, StateFilter(AuthFlow.waiting_password), F.text)

    dp.include_router(settings_panel.router)
    dp.include_router(post.router)


def create_bot() -> Bot:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")
    return Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def get_dispatcher() -> Dispatcher:
    """Build dispatcher for the current event loop (serverless-safe)."""
    global _dispatcher
    async with _get_dispatcher_lock():
        if _dispatcher is None:
            pool = await get_pool()
            await db_seed_settings_from_json()
            dp = Dispatcher(storage=PostgreSQLStorage(pool))
            _wire_dispatcher(dp)
            _dispatcher = dp
            log.info("Dispatcher initialized.")
    return _dispatcher


async def create_bot_and_dispatcher():
    """Persistent bot + dispatcher — used for local long-polling."""
    bot = create_bot()
    dp = await get_dispatcher()
    return bot, dp


async def setup_webhook(bot: Bot) -> None:
    """Register the webhook URL with Telegram."""
    from config import WEBHOOK_SECRET

    url = get_webhook_url()
    await bot.set_webhook(
        url=url,
        secret_token=WEBHOOK_SECRET or None,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )
    await _set_commands(bot)
    log.info("Webhook set to %s", url)


# ── Local long-polling ────────────────────────────────────────────────────────

async def main() -> None:
    bot, dp = await create_bot_and_dispatcher()

    await bot.delete_webhook(drop_pending_updates=True)
    await _set_commands(bot)

    port = int(os.getenv("PORT", "8080"))
    await start_web_server(port=port)

    log.info("Bot started in polling mode. Password auth enabled.")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
        )
    finally:
        await bot.session.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
