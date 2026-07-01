"""Redis TLS helpers for Vercel + Upstash."""
import os
import ssl
from typing import Any, Dict, Optional

from config import REDIS_URL


def redis_connection_kwargs() -> Dict[str, Any]:
    """
    Upstash uses rediss:// (TLS). Vercel's Python runtime has no system CA bundle,
    which causes CERTIFICATE_VERIFY_FAILED unless we pass an explicit SSL context.
    """
    if not REDIS_URL.startswith("rediss://"):
        return {}

    ctx = ssl.create_default_context()
    if os.environ.get("VERCEL"):
        # Encrypted, but skip CA verify — required on Vercel serverless + Upstash
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

    return {"ssl": ctx}


def ensure_rediss_url(url: str) -> str:
    """Upstash TLS URLs must use rediss:// (note the double s)."""
    if url.startswith("redis://") and not url.startswith("rediss://"):
        return url.replace("redis://", "rediss://", 1)
    return url
