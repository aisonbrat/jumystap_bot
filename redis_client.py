"""Redis connection helpers for Upstash on Vercel."""
import ssl
from typing import Any, Dict

from config import REDIS_URL


def redis_connection_kwargs() -> Dict[str, Any]:
    """
    Upstash uses rediss:// (TLS).

    Do NOT pass ssl=SSLContext here — rediss:// already enables TLS and an extra
    ssl object breaks redis-py (AbstractConnection.__init__ error on Vercel).

    Vercel has no CA bundle, so disable certificate verification for Upstash TLS.
    """
    if not REDIS_URL.startswith("rediss://"):
        return {}
    return {
        "ssl_cert_reqs": ssl.CERT_NONE,
        "ssl_check_hostname": False,
    }


def redis_from_url_kwargs(*, decode_responses: bool) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"decode_responses": decode_responses}
    kwargs.update(redis_connection_kwargs())
    return kwargs
