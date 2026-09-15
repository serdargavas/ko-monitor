"""Same-origin check for requests CORS does not protect (WebSockets, form-style POSTs)."""

from collections.abc import Mapping
from urllib.parse import urlsplit


def origin_allowed(headers: Mapping[str, str]) -> bool:
    """True without an Origin header (navigations, curl); otherwise its host[:port] must equal Host.

    headers must look names up case-insensitively (Starlette's Headers does).
    """
    origin = headers.get("origin")
    if origin is None:
        return True
    try:
        netloc = urlsplit(origin).netloc
    except ValueError:
        return False
    return bool(netloc) and netloc.lower() == headers.get("host", "").lower()
