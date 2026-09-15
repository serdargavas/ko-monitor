import re
from pathlib import Path

from ko_monitor.vapid import application_server_key, ensure_vapid_key


def test_key_is_created_once_and_public_key_is_base64url(tmp_path: Path):
    path = tmp_path / "data" / "vapid_private.pem"
    assert ensure_vapid_key(path) == path
    content = path.read_bytes()
    ensure_vapid_key(path)
    assert path.read_bytes() == content
    key = application_server_key(path)
    assert len(key) == 87
    assert re.fullmatch(r"[A-Za-z0-9_-]+", key)
