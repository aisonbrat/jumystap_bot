"""
Password-based authentication persisted in PostgreSQL.

Uses an outer middleware so auth is enforced before any handler runs.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database import db_authenticate, db_is_authenticated, db_revoke_authentication
from states import AuthFlow


async def authenticate(user_id: int) -> None:
    await db_authenticate(user_id)


async def is_authenticated(user_id: int) -> bool:
    return await db_is_authenticated(user_id)


async def logout(user_id: int) -> None:
    await db_revoke_authentication(user_id)


async def _is_authenticated_cached(user_id: int, data: Dict[str, Any]) -> bool:
    """One DB lookup per update (middleware may call this multiple times)."""
    cache: Dict[int, bool] = data.setdefault("_auth_cache", {})
    if user_id not in cache:
        cache[user_id] = await is_authenticated(user_id)
    return cache[user_id]


class AuthMiddleware(BaseMiddleware):
    """
    Outer middleware — runs before every message / callback_query handler.

    Rules:
      /start command  → always let through (so the user can authenticate)
      /logout command → always let through (so logout works from any state)
      waiting_password state → let through (so password reply is processed)
      authenticated user     → let through
      everyone else          → block and ask for /start
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)

        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)

        if isinstance(event, Message) and event.text and event.text.startswith("/logout"):
            return await handler(event, data)

        fsm: Any = data.get("state")
        if fsm is not None:
            current = await fsm.get_state()
            if current == AuthFlow.waiting_password.state:
                return await handler(event, data)

        if user and await _is_authenticated_cached(user.id, data):
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer("🔐 Send /start and enter the password to use this bot.")
        elif isinstance(event, CallbackQuery):
            await event.answer("🔐 Not authenticated. Send /start.", show_alert=True)
        return None
