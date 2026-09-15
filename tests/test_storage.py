from pathlib import Path

import pytest

from ko_monitor.models import Event, EventKind, Snapshot, State
from ko_monitor.storage import Storage


@pytest.fixture
def storage(tmp_path: Path):
    s = Storage(tmp_path / "sub" / "db.sqlite3")
    yield s
    s.close()


def make_snapshot(ts: float, state: State = State.ALIVE) -> Snapshot:
    return Snapshot(ts, state, 9718, 9996, "Ronark Land", 1_000_000, 20, 28, ts - 5)


def test_creates_parent_directory(tmp_path: Path):
    s = Storage(tmp_path / "a" / "b" / "db.sqlite3")
    s.close()
    assert (tmp_path / "a" / "b" / "db.sqlite3").exists()


def test_snapshots_roundtrip_and_prune(storage: Storage):
    storage.add_snapshot(make_snapshot(100.0))
    storage.add_snapshot(make_snapshot(200.0, State.DEAD))
    assert storage.snapshots_since(150.0) == [make_snapshot(200.0, State.DEAD)]
    assert storage.prune_snapshots(older_than=150.0) == 1
    assert [s.ts for s in storage.snapshots_since(0.0)] == [200.0]


def test_events_are_stored_newest_first_and_marked(storage: Storage):
    first = storage.add_event(Event(EventKind.GAME_STARTED, 10.0))
    second = storage.add_event(Event(EventKind.DEAD, 20.0, "Ronark Land", notify=True))
    storage.mark_notified(second, at=21.0)
    events = storage.recent_events(limit=10)
    assert [e["id"] for e in events] == [second, first]
    assert events[0] == {
        "id": second, "ts": 20.0, "kind": "dead", "detail": "Ronark Land",
        "notified": True, "notified_at": 21.0,
    }
    assert events[1]["notified"] is False


def test_subscriptions_upsert_and_delete(storage: Storage):
    storage.add_subscription("https://push/1", {"p256dh": "a", "auth": "b"}, now=1.0)
    storage.add_subscription("https://push/1", {"p256dh": "c", "auth": "d"}, now=2.0)
    storage.add_subscription("https://push/2", {"p256dh": "e", "auth": "f"}, now=3.0)
    assert storage.subscriptions() == [
        {"endpoint": "https://push/1", "keys": {"p256dh": "c", "auth": "d"}},
        {"endpoint": "https://push/2", "keys": {"p256dh": "e", "auth": "f"}},
    ]
    storage.delete_subscription("https://push/1")
    assert [s["endpoint"] for s in storage.subscriptions()] == ["https://push/2"]
