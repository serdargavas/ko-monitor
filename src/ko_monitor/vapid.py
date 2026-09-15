from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02
from py_vapid.utils import b64urlencode


def ensure_vapid_key(path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Vapid02()
        key.generate_keys()
        key.save_key(str(path))
    return path


def application_server_key(path: Path) -> str:
    """Public key in the form the browser's pushManager.subscribe() expects."""
    key = Vapid02.from_file(str(path))
    raw = key.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64urlencode(raw)
