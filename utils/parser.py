"""
Regex-based extractor for contact information embedded in vacancy text.

Supported contact types (in priority order):
  1. Kazakh/Russian phone  →  WhatsApp button
  2. Telegram @handle or t.me/ link  →  Telegram button
  3. Instagram profile URL  →  Instagram button
"""
import re
from dataclasses import dataclass, asdict
from typing import Optional

# ── Patterns ────────────────────────────────────────────────────────────────

# Matches explicit WhatsApp links: wa.me/77001234567 | wa.me/+77001234567
# Checked BEFORE PHONE_RE so a wa.me link in the text always becomes the WA button.
WA_RE = re.compile(
    r'(?:https?://)?wa\.me/(\+?\d{10,15})'
)

# Matches: +77079237006 | 77079237006 | 87079237006 | 8-707-923-70-06 (with separators)
# Requires exactly 11 digits (KZ/RU format) after stripping non-digits.
PHONE_RE = re.compile(
    r'(?<!\d)'
    r'(\+?[78][\s\-\(]?\d{3}[\s\-\(]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})'
    r'(?!\d)'
)

# Matches: t.me/username | telegram.me/username | @username
# Excludes common non-user paths: joinchat, +invite_hash handled separately
TELEGRAM_RE = re.compile(
    r'(?:https?://)?t(?:elegram)?\.me/([A-Za-z0-9_]{4,32})'
    r'|'
    r'(?<![/@\w])@([A-Za-z0-9_]{4,32})'
)

# Matches: instagram.com/username | www.instagram.com/username
# Username must be at least 1 char; trailing slash or query string are ignored.
INSTAGRAM_RE = re.compile(
    r'(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,50})(?:[/?]|$)'
)


# ── Data class ───────────────────────────────────────────────────────────────

@dataclass
class Contacts:
    phone: Optional[str] = None       # Normalized: +7XXXXXXXXXX
    telegram: Optional[str] = None    # Full URL:   https://t.me/username
    instagram: Optional[str] = None   # Full URL:   https://www.instagram.com/username/


# ── Helpers ──────────────────────────────────────────────────────────────────

def normalize_phone(raw: str) -> str:
    """Strip formatting and return +7XXXXXXXXXX (11-digit KZ/RU standard)."""
    digits = re.sub(r"\D", "", raw)
    # 8XXXXXXXXXX → 7XXXXXXXXXX
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    # XXXXXXXXXX (10 digits, no country code) → 7XXXXXXXXXX
    elif len(digits) == 10:
        digits = "7" + digits
    # Keep only last 11 digits as a safety clamp
    return "+" + digits[-11:]


def parse_contacts(text: str) -> Contacts:
    """Extract the first occurrence of each contact type from *text*."""
    c = Contacts()

    # Explicit wa.me link takes priority over a bare phone number
    m = WA_RE.search(text)
    if m:
        c.phone = normalize_phone(m.group(1))
    else:
        m = PHONE_RE.search(text)
        if m:
            c.phone = normalize_phone(m.group(1))

    m = TELEGRAM_RE.search(text)
    if m:
        username = (m.group(1) or m.group(2)).strip("/")
        c.telegram = f"https://t.me/{username}"

    m = INSTAGRAM_RE.search(text)
    if m:
        username = m.group(1).strip("/")
        c.instagram = f"https://www.instagram.com/{username}/"

    return c


# ── WhatsApp link injection ──────────────────────────────────────────────────

def inject_wa_link(html_text: str, contacts: Contacts) -> str:
    """
    Find the phone number inside the HTML post body and insert a clickable
    'WhatsApp сілтеме' hyperlink on the very next line after it.

    Skipped if the text already contains a wa.me link so we never duplicate it.
    """
    if not contacts.phone:
        return html_text

    # Don't inject if the post already has a WhatsApp link
    if "wa.me/" in html_text:
        return html_text

    wa_number = contacts.phone.lstrip("+")
    wa_url = f"https://wa.me/{wa_number}"
    wa_link = f'<a href="{wa_url}">WhatsApp сілтеме</a>'

    # Find the raw phone string in the HTML text and insert the link after it
    match = PHONE_RE.search(html_text)
    if not match:
        return html_text

    insert_pos = match.end()
    return html_text[:insert_pos] + "\n" + wa_link + html_text[insert_pos:]


# ── Serialization (for FSMContext storage) ───────────────────────────────────

def contacts_to_dict(c: Contacts) -> dict:
    return asdict(c)


def contacts_from_dict(d: dict) -> Contacts:
    return Contacts(**d)
