"""Telegram API helpers — ignore harmless 'message is not modified' errors."""
from typing import Any, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, LinkPreviewOptions, Message


def _is_not_modified(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in str(exc).lower()


async def safe_edit_text(
    message: Message,
    text: str,
    *,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    link_preview_options: Optional[LinkPreviewOptions] = None,
    **kwargs: Any,
) -> Optional[Message]:
    try:
        return await message.edit_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            link_preview_options=link_preview_options,
            **kwargs,
        )
    except TelegramBadRequest as exc:
        if _is_not_modified(exc):
            return None
        raise


async def safe_edit_message_text(
    bot: Bot,
    *,
    chat_id: int,
    message_id: int,
    text: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    link_preview_options: Optional[LinkPreviewOptions] = None,
    **kwargs: Any,
) -> Optional[Any]:
    try:
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            link_preview_options=link_preview_options,
            **kwargs,
        )
    except TelegramBadRequest as exc:
        if _is_not_modified(exc):
            return None
        raise


async def safe_edit_message_caption(
    bot: Bot,
    *,
    chat_id: int,
    message_id: int,
    caption: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs: Any,
) -> Optional[Any]:
    try:
        return await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )
    except TelegramBadRequest as exc:
        if _is_not_modified(exc):
            return None
        raise


async def safe_edit_message_reply_markup(
    bot: Bot,
    *,
    chat_id: int,
    message_id: int,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs: Any,
) -> Optional[Any]:
    try:
        return await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            **kwargs,
        )
    except TelegramBadRequest as exc:
        if _is_not_modified(exc):
            return None
        raise
