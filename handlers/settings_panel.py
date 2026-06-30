"""
/settings command and the inline settings menu.

All changes are persisted immediately to settings.json via utils.store.
"""
import html

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from states import PostFlow, SettingsFlow
from utils import store
from utils.keyboards import build_settings_menu

router = Router(name="settings")


# ── Helper ────────────────────────────────────────────────────────────────────

async def _settings_text() -> str:
    s = await store.get()
    return (
        "⚙️ <b>Bot Settings</b>\n\n"
        f"📢 Channel: <code>{html.escape(s['channel_id'] or 'not set')}</code>\n"
        f"🔤 Button text: <code>{html.escape(s['permanent_button_text'])}</code>\n"
        f"🔗 Button URL: <code>{html.escape(s['permanent_button_url'])}</code>\n\n"
        f"📝 Footer:\n<pre>{html.escape(s['footer'])}</pre>"
    )


# ── Entry ─────────────────────────────────────────────────────────────────────

@router.message(Command("settings"), StateFilter(None))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    await message.answer(
        await _settings_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=build_settings_menu(),
    )
    await state.set_state(SettingsFlow.menu)


# Block /settings while a post is being edited
@router.message(Command("settings"), StateFilter(PostFlow))
async def settings_blocked(message: Message) -> None:
    await message.answer(
        "⚠️ Please finish or cancel the current post (/cancel) before changing settings.",
        parse_mode=ParseMode.HTML,
    )


# ── Close ─────────────────────────────────────────────────────────────────────

@router.callback_query(SettingsFlow.menu, F.data == "set:close")
async def on_close(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.clear()
    await query.message.delete()


# ── Edit footer ───────────────────────────────────────────────────────────────

@router.callback_query(SettingsFlow.menu, F.data == "set:footer")
async def on_edit_footer(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.set_state(SettingsFlow.edit_footer)
    await query.message.edit_text(
        "📝 <b>Send the new footer text.</b>\n\n"
        "Line breaks and emojis are supported.\n"
        "/cancel to cancel",
        parse_mode=ParseMode.HTML,
    )


@router.message(SettingsFlow.edit_footer, F.text)
async def save_footer(message: Message, state: FSMContext) -> None:
    await store.save(footer=message.text)
    await state.set_state(SettingsFlow.menu)
    await message.answer(
        f"✅ Footer updated!\n\n{await _settings_text()}",
        parse_mode=ParseMode.HTML,
        reply_markup=build_settings_menu(),
    )


# ── Edit permanent button text ────────────────────────────────────────────────

@router.callback_query(SettingsFlow.menu, F.data == "set:perm_text")
async def on_edit_perm_text(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.set_state(SettingsFlow.edit_perm_text)
    await query.message.edit_text(
        '🔤 <b>Send the new button text for "POST A JOB".</b>\n\n/cancel to cancel',
        parse_mode=ParseMode.HTML,
    )


@router.message(SettingsFlow.edit_perm_text, F.text)
async def save_perm_text(message: Message, state: FSMContext) -> None:
    await store.save(permanent_button_text=message.text.strip())
    await state.set_state(SettingsFlow.menu)
    await message.answer(
        f"✅ Button text updated!\n\n{await _settings_text()}",
        parse_mode=ParseMode.HTML,
        reply_markup=build_settings_menu(),
    )


# ── Edit permanent button URL ─────────────────────────────────────────────────

@router.callback_query(SettingsFlow.menu, F.data == "set:perm_url")
async def on_edit_perm_url(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.set_state(SettingsFlow.edit_perm_url)
    await query.message.edit_text(
        '🔗 <b>Send the new URL for the "POST A JOB" button.</b>\n\n'
        "Format: <code>https://t.me/username</code>\n/cancel to cancel",
        parse_mode=ParseMode.HTML,
    )


@router.message(SettingsFlow.edit_perm_url, F.text)
async def save_perm_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not url.startswith(("http://", "https://", "t.me/")):
        await message.answer(
            "⚠️ Invalid URL. Must start with <code>https://</code> or <code>t.me/</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    # Normalize t.me/ → https://t.me/
    if url.startswith("t.me/"):
        url = "https://" + url
    await store.save(permanent_button_url=url)
    await state.set_state(SettingsFlow.menu)
    await message.answer(
        f"✅ Button URL updated!\n\n{await _settings_text()}",
        parse_mode=ParseMode.HTML,
        reply_markup=build_settings_menu(),
    )


# ── Edit channel ID ───────────────────────────────────────────────────────────

@router.callback_query(SettingsFlow.menu, F.data == "set:channel")
async def on_edit_channel(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.set_state(SettingsFlow.edit_channel)
    await query.message.edit_text(
        "📢 <b>Send the channel ID or @username.</b>\n\n"
        "Example: <code>@jumystap1</code> or <code>-1001234567890</code>\n\n"
        "The bot must be an Administrator of the channel with Post Messages permission.\n"
        "/cancel to cancel",
        parse_mode=ParseMode.HTML,
    )


@router.message(SettingsFlow.edit_channel, F.text)
async def save_channel(message: Message, state: FSMContext) -> None:
    channel = message.text.strip()
    await store.save(channel_id=channel)
    await state.set_state(SettingsFlow.menu)
    await message.answer(
        f"✅ Channel set: <code>{html.escape(channel)}</code>\n\n{await _settings_text()}",
        parse_mode=ParseMode.HTML,
        reply_markup=build_settings_menu(),
    )


# ── /cancel inside settings flow ─────────────────────────────────────────────

@router.message(Command("cancel"), StateFilter(SettingsFlow))
async def cancel_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Settings closed.")
