"""
All InlineKeyboardMarkup builders used by the bot.
"""
from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.parser import Contacts

# Pre-filled message used for BOTH WhatsApp and Telegram buttons.
_PREFILL = (
    "Сәлеметсіз бе, вакансия бойынша жазып тұрмын.\n\n"
    "✨ JumysTap телеграм каналынан – https://t.me/jumystap1/"
)
_PREFILL_ENCODED = quote(_PREFILL, safe="")


# ── Post reply markup (shown in the channel / preview) ──────────────────────

def build_post_markup(
    contacts: Contacts,
    perm_text: str,
    perm_url: str,
    buttons_visible: bool = True,
) -> InlineKeyboardMarkup:
    """
    Stacks contact buttons vertically in priority order, always ending with
    the permanent 'ВАКАНСИЯ ШЫҒАРУ' button.

    Priority: WhatsApp (phone) → Telegram → Instagram → permanent
    """
    builder = InlineKeyboardBuilder()

    if buttons_visible:
        if contacts.phone:
            # wa.me expects number without leading +; append pre-filled message
            wa_number = contacts.phone.lstrip("+")
            builder.row(InlineKeyboardButton(
                text="🟢 ВАТСАПҚА ЖАЗУ",
                url=f"https://wa.me/{wa_number}?text={_PREFILL_ENCODED}",
            ))

        if contacts.telegram:
            # tg://resolve opens the Telegram chat and pre-fills the composer
            tg_username = contacts.telegram.rstrip("/").split("/")[-1]
            builder.row(InlineKeyboardButton(
                text="🔵 ТЕЛЕГРАМ",
                url=f"tg://resolve?domain={tg_username}&text={_PREFILL_ENCODED}",
            ))

        if contacts.instagram:
            builder.row(InlineKeyboardButton(
                text="🟣 КОМПАНИЯ ИНСТАГРАМЫ",
                url=contacts.instagram,
            ))

    # Always present at the bottom
    builder.row(InlineKeyboardButton(text=perm_text, url=perm_url))

    return builder.as_markup()


# ── Admin control panel ──────────────────────────────────────────────────────

def build_control_panel(link_preview_disabled: bool) -> InlineKeyboardMarkup:
    """Shown to the admin below the preview message."""
    preview_label = (
        "🔗 Link Preview: OFF  →  turn ON"
        if link_preview_disabled
        else "🔗 Link Preview: ON   →  turn OFF"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🟢 Publish to Channel", callback_data="ctrl:publish"))
    builder.row(InlineKeyboardButton(
        text="🖼 Add / Change Photo", callback_data="ctrl:add_photo"))
    builder.row(InlineKeyboardButton(
        text=preview_label, callback_data="ctrl:toggle_preview"))
    builder.row(InlineKeyboardButton(
        text="❌ Delete Buttons", callback_data="ctrl:delete_buttons"))
    builder.row(InlineKeyboardButton(
        text="⚙ Edit Buttons Manually", callback_data="ctrl:edit_buttons"))
    return builder.as_markup()


# ── Publish confirmation ─────────────────────────────────────────────────────

def build_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Yes, Publish!", callback_data="ctrl:confirm_yes"),
        InlineKeyboardButton(
            text="↩ Go Back", callback_data="ctrl:confirm_no"),
    )
    return builder.as_markup()


# ── Settings menu ────────────────────────────────────────────────────────────

def build_settings_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📝 Edit Footer", callback_data="set:footer"))
    builder.row(InlineKeyboardButton(
        text='🔤 Button Text ("POST A JOB")', callback_data="set:perm_text"))
    builder.row(InlineKeyboardButton(
        text='🔗 Button URL ("POST A JOB")', callback_data="set:perm_url"))
    builder.row(InlineKeyboardButton(
        text="📢 Set Channel ID / @username", callback_data="set:channel"))
    builder.row(InlineKeyboardButton(
        text="❌ Close", callback_data="set:close"))
    return builder.as_markup()
