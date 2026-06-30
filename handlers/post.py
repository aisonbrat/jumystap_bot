"""
Post creation workflow (FSM).

Flow:
  Admin sends text
      → bot parses contacts, shows preview + control panel
      → Admin uses control panel callbacks to:
            publish / add photo / toggle link preview /
            delete contact buttons / edit buttons manually
"""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InputMediaPhoto,
    LinkPreviewOptions,
    Message,
)

from states import PostFlow
from utils import parser, store
from utils.keyboards import (
    build_confirm_keyboard,
    build_control_panel,
    build_post_markup,
)
from utils.telegram import (
    safe_edit_message_caption,
    safe_edit_message_reply_markup,
    safe_edit_message_text,
    safe_edit_text,
)

log = logging.getLogger(__name__)

router = Router(name="post")

# ── Helpers ──────────────────────────────────────────────────────────────────

CTRL_HEADER = "📋 <b>Post Control Panel:</b>"

_REQUIRED_POST_KEYS = ("contacts", "html_text", "preview_msg_id", "ctrl_msg_id")


def _has_post_data(data: dict) -> bool:
    return all(k in data for k in _REQUIRED_POST_KEYS)


def _build_full_html(html_text: str, footer: str) -> str:
    """Append plain-text footer to the HTML-formatted post body."""
    return f"{html_text}\n\n{html.escape(footer)}"


async def _send_initial_preview(
    bot: Bot,
    chat_id: int,
    data: dict,
    settings: dict,
) -> tuple[int, int]:
    """
    Send the preview message + control panel.
    Returns (preview_msg_id, ctrl_msg_id).
    """
    contacts = parser.contacts_from_dict(data["contacts"])
    full_html = _build_full_html(data["html_text"], settings["footer"])
    post_kb = build_post_markup(
        contacts,
        settings["permanent_button_text"],
        settings["permanent_button_url"],
        data["buttons_visible"],
    )
    lp = LinkPreviewOptions(is_disabled=data["link_preview_disabled"])

    if data["photo_id"]:
        prev = await bot.send_photo(
            chat_id,
            data["photo_id"],
            caption=full_html,
            parse_mode=ParseMode.HTML,
            reply_markup=post_kb,
        )
    else:
        prev = await bot.send_message(
            chat_id,
            full_html,
            parse_mode=ParseMode.HTML,
            reply_markup=post_kb,
            link_preview_options=lp,
        )

    ctrl = await bot.send_message(
        chat_id,
        CTRL_HEADER,
        parse_mode=ParseMode.HTML,
        reply_markup=build_control_panel(data["link_preview_disabled"]),
    )
    return prev.message_id, ctrl.message_id


async def _refresh_preview(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Re-render both preview and control panel in-place (edit existing messages)."""
    data = await state.get_data()
    if not _has_post_data(data):
        return
    settings = await store.get()
    contacts = parser.contacts_from_dict(data["contacts"])
    full_html = _build_full_html(data["html_text"], settings["footer"])
    post_kb = build_post_markup(
        contacts,
        settings["permanent_button_text"],
        settings["permanent_button_url"],
        data["buttons_visible"],
    )
    lp = LinkPreviewOptions(is_disabled=data["link_preview_disabled"])

    if data["photo_id"]:
        await safe_edit_message_caption(
            bot,
            chat_id=chat_id,
            message_id=data["preview_msg_id"],
            caption=full_html,
            parse_mode=ParseMode.HTML,
            reply_markup=post_kb,
        )
    else:
        await safe_edit_message_text(
            bot,
            chat_id=chat_id,
            message_id=data["preview_msg_id"],
            text=full_html,
            parse_mode=ParseMode.HTML,
            reply_markup=post_kb,
            link_preview_options=lp,
        )

    await safe_edit_message_reply_markup(
        bot,
        chat_id=chat_id,
        message_id=data["ctrl_msg_id"],
        reply_markup=build_control_panel(data["link_preview_disabled"]),
    )


async def _restore_ctrl_panel(bot: Bot, chat_id: int, data: dict) -> None:
    """Restore the control panel message after it was temporarily replaced."""
    if not data.get("ctrl_msg_id"):
        return
    await safe_edit_message_text(
        bot,
        chat_id=chat_id,
        message_id=data["ctrl_msg_id"],
        text=CTRL_HEADER,
        parse_mode=ParseMode.HTML,
        reply_markup=build_control_panel(data.get("link_preview_disabled", True)),
    )


# ── Entry: admin sends raw post text ─────────────────────────────────────────

@router.message(StateFilter(None), F.text)
async def handle_new_post(message: Message, state: FSMContext, bot: Bot) -> None:
    settings = await store.get()

    # message.html_text preserves bold/italic/underline/mono from Telegram entities
    html_text = message.html_text
    contacts = parser.parse_contacts(message.text or "")

    # Inject a clickable WhatsApp link on the line right after the phone number
    html_text = parser.inject_wa_link(html_text, contacts)

    init_data: dict = {
        "html_text": html_text,
        "photo_id": None,
        "contacts": parser.contacts_to_dict(contacts),
        "buttons_visible": True,
        "link_preview_disabled": True,  # OFF by default per requirements
        "preview_msg_id": 0,
        "ctrl_msg_id": 0,
    }

    prev_id, ctrl_id = await _send_initial_preview(bot, message.chat.id, init_data, settings)
    init_data["preview_msg_id"] = prev_id
    init_data["ctrl_msg_id"] = ctrl_id

    await state.set_data(init_data)
    await state.set_state(PostFlow.reviewing)


# Guard: plain text sent while already reviewing a post.
# Excludes commands (messages starting with '/') so /cancel still works.
@router.message(PostFlow.reviewing, F.text, lambda m: not (m.text or "").startswith("/"))
async def guard_reviewing_text(message: Message) -> None:
    await message.answer(
        "⚠️ You already have a post in review.\n"
        "Use the control panel below or /cancel to discard it.",
        parse_mode=ParseMode.HTML,
    )
    await message.delete()


# ── Control panel: Publish ────────────────────────────────────────────────────

@router.callback_query(PostFlow.reviewing, F.data == "ctrl:publish")
async def on_publish(query: CallbackQuery) -> None:
    await query.answer()
    await safe_edit_text(
        query.message,
        "❓ <b>Publish this post to the channel?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=build_confirm_keyboard(),
    )


@router.callback_query(PostFlow.reviewing, F.data == "ctrl:confirm_yes")
async def on_confirm_yes(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if not _has_post_data(data):
        await query.answer("Session expired. Send a new post.", show_alert=True)
        return
    if data.get("publishing"):
        await query.answer("Already publishing…", show_alert=False)
        return

    await query.answer()
    await state.update_data(publishing=True)

    settings = await store.get()
    channel_id = settings["channel_id"]

    if not channel_id:
        await state.update_data(publishing=False)
        await safe_edit_text(
            query.message,
            "⚠️ <b>Channel ID is not set!</b>\n"
            "Go to /settings → 📢 Set Channel ID / @username",
            parse_mode=ParseMode.HTML,
        )
        return

    contacts = parser.contacts_from_dict(data["contacts"])
    full_html = _build_full_html(data["html_text"], settings["footer"])
    post_kb = build_post_markup(
        contacts,
        settings["permanent_button_text"],
        settings["permanent_button_url"],
        data["buttons_visible"],
    )
    lp = LinkPreviewOptions(is_disabled=data["link_preview_disabled"])

    try:
        if data["photo_id"]:
            await bot.send_photo(
                channel_id,
                data["photo_id"],
                caption=full_html,
                parse_mode=ParseMode.HTML,
                reply_markup=post_kb,
            )
        else:
            await bot.send_message(
                channel_id,
                full_html,
                parse_mode=ParseMode.HTML,
                reply_markup=post_kb,
                link_preview_options=lp,
            )
    except Exception as exc:
        log.error("Publish failed: %s", exc)
        await state.update_data(publishing=False)
        await safe_edit_text(
            query.message,
            f"❌ <b>Publish failed:</b>\n<code>{html.escape(str(exc))}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Clean up preview + control messages
    try:
        await bot.delete_message(query.message.chat.id, data["preview_msg_id"])
    except Exception:
        pass
    await safe_edit_text(
        query.message,
        "✅ <b>Post published successfully!</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=None,
    )
    await state.clear()


@router.callback_query(PostFlow.reviewing, F.data == "ctrl:confirm_no")
async def on_confirm_no(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await query.answer()
    data = await state.get_data()
    if not _has_post_data(data):
        return
    await _restore_ctrl_panel(bot, query.message.chat.id, data)


# ── Control panel: Add / Change Photo ────────────────────────────────────────

@router.callback_query(PostFlow.reviewing, F.data == "ctrl:add_photo")
async def on_add_photo_prompt(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.set_state(PostFlow.waiting_photo)
    await safe_edit_text(
        query.message,
        "🖼 <b>Send a photo for this post.</b>\n\n/cancel to cancel",
        parse_mode=ParseMode.HTML,
    )


@router.message(PostFlow.waiting_photo, F.photo)
async def on_photo_received(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if not _has_post_data(data):
        await message.answer("Session expired. Send a new post.")
        await state.clear()
        return

    file_id = message.photo[-1].file_id  # largest resolution
    settings = await store.get()

    contacts = parser.contacts_from_dict(data["contacts"])
    full_html = _build_full_html(data["html_text"], settings["footer"])
    post_kb = build_post_markup(
        contacts,
        settings["permanent_button_text"],
        settings["permanent_button_url"],
        data["buttons_visible"],
    )

    if data["photo_id"]:
        # Already a photo preview → edit media in-place
        await bot.edit_message_media(
            chat_id=message.chat.id,
            message_id=data["preview_msg_id"],
            media=InputMediaPhoto(
                media=file_id,
                caption=full_html,
                parse_mode=ParseMode.HTML,
            ),
            reply_markup=post_kb,
        )
    else:
        # Currently a text preview → delete it and send a photo instead
        try:
            await bot.delete_message(message.chat.id, data["preview_msg_id"])
        except Exception:
            pass
        new_prev = await bot.send_photo(
            message.chat.id,
            file_id,
            caption=full_html,
            parse_mode=ParseMode.HTML,
            reply_markup=post_kb,
        )
        data["preview_msg_id"] = new_prev.message_id

    data["photo_id"] = file_id
    await message.delete()
    await state.set_state(PostFlow.reviewing)
    await state.set_data(data)
    await _restore_ctrl_panel(bot, message.chat.id, data)


@router.message(PostFlow.waiting_photo, ~F.photo)
async def on_waiting_photo_wrong(message: Message) -> None:
    await message.answer("⚠️ Please send a <b>photo</b>. /cancel to cancel.",
                         parse_mode=ParseMode.HTML)
    await message.delete()


# ── Control panel: Toggle Link Preview ───────────────────────────────────────

@router.callback_query(PostFlow.reviewing, F.data == "ctrl:toggle_preview")
async def on_toggle_preview(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await query.answer()
    data = await state.get_data()
    if not _has_post_data(data):
        return
    data["link_preview_disabled"] = not data["link_preview_disabled"]
    await state.set_data(data)
    await _refresh_preview(bot, query.message.chat.id, state)


# ── Control panel: Delete Contact Buttons ────────────────────────────────────

@router.callback_query(PostFlow.reviewing, F.data == "ctrl:delete_buttons")
async def on_delete_buttons(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await query.answer("Contact buttons removed", show_alert=False)
    data = await state.get_data()
    if not _has_post_data(data):
        return
    data["buttons_visible"] = False
    await state.set_data(data)
    await _refresh_preview(bot, query.message.chat.id, state)


# ── Control panel: Edit Buttons Manually ─────────────────────────────────────

@router.callback_query(PostFlow.reviewing, F.data == "ctrl:edit_buttons")
async def on_edit_buttons_prompt(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    data = await state.get_data()
    if not _has_post_data(data):
        return
    c = parser.contacts_from_dict(data["contacts"])

    text = (
        "✏️ <b>Edit Buttons</b>\n\n"
        "Current values:\n"
        f"  📱 Phone (WA):  <code>{html.escape(c.phone or 'not set')}</code>\n"
        f"  💬 Telegram:    <code>{html.escape(c.telegram or 'not set')}</code>\n"
        f"  📸 Instagram:   <code>{html.escape(c.instagram or 'not set')}</code>\n\n"
        "Send corrections line by line:\n"
        "<code>phone: +77079237006</code>\n"
        "<code>telegram: https://t.me/username</code>\n"
        "<code>instagram: https://www.instagram.com/username/</code>\n\n"
        "To remove a button: <code>phone: -</code>\n"
        "/cancel to cancel"
    )
    await state.set_state(PostFlow.editing_buttons)
    await safe_edit_text(query.message, text, parse_mode=ParseMode.HTML)


@router.message(PostFlow.editing_buttons, F.text)
async def on_edit_buttons_input(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text.strip().startswith("/"):
        return  # let /cancel be handled below

    data = await state.get_data()
    if not _has_post_data(data):
        await message.answer("Session expired. Send a new post.")
        await state.clear()
        return

    c = parser.contacts_from_dict(data["contacts"])

    for line in message.text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        remove = value in ("-", "no", "none", "")

        if key == "phone":
            c.phone = None if remove else parser.normalize_phone(value)
        elif key == "telegram":
            if remove:
                c.telegram = None
            elif value.startswith("http"):
                c.telegram = value
            else:
                c.telegram = f"https://t.me/{value.lstrip('@').lstrip('/')}"
        elif key == "instagram":
            if remove:
                c.instagram = None
            elif value.startswith("http"):
                c.instagram = value
            else:
                c.instagram = f"https://www.instagram.com/{value.lstrip('/')}/"

    data["contacts"] = parser.contacts_to_dict(c)
    data["buttons_visible"] = True
    await state.set_state(PostFlow.reviewing)
    await state.set_data(data)

    try:
        await message.delete()
    except Exception:
        pass

    await _refresh_preview(bot, message.chat.id, state)
    await _restore_ctrl_panel(bot, message.chat.id, data)


# ── /cancel — abort current flow ─────────────────────────────────────────────

@router.message(Command("cancel"), StateFilter(PostFlow))
async def on_cancel(message: Message, state: FSMContext, bot: Bot) -> None:
    current = await state.get_state()
    data = await state.get_data()

    if current in (PostFlow.waiting_photo, PostFlow.editing_buttons):
        # Return to reviewing: restore ctrl panel, keep preview intact
        await state.set_state(PostFlow.reviewing)
        await _restore_ctrl_panel(bot, message.chat.id, data)
        try:
            await message.delete()
        except Exception:
            pass
        return

    # Full abort: delete preview and control messages
    for msg_id in (data.get("preview_msg_id"), data.get("ctrl_msg_id")):
        if msg_id:
            try:
                await bot.delete_message(message.chat.id, msg_id)
            except Exception:
                pass

    await state.clear()
    await message.answer("❌ <b>Post cancelled.</b>", parse_mode=ParseMode.HTML)
