from datetime import datetime

from ko_monitor.messages import render
from ko_monitor.models import Event, EventKind


def test_render_with_zone():
    ts = datetime(2026, 9, 15, 11, 42).timestamp()
    assert render(Event(EventKind.DEAD, ts, "Ronark Land", notify=True)) == {
        "title": "💀 Karakter öldü",
        "body": "Ronark Land · 11:42",
        "url": "/#/events",
        "kind": "dead",
        "ts": ts,
    }


def test_render_without_detail():
    ts = datetime(2026, 9, 15, 8, 5).timestamp()
    message = render(Event(EventKind.GAME_CLOSED, ts, notify=True))
    assert (message["title"], message["body"]) == ("❌ Oyun kapandı", "08:05")


def test_every_notifying_kind_has_a_title():
    for kind in (EventKind.DEAD, EventKind.INVENTORY_FULL, EventKind.DISCONNECTED,
                 EventKind.GAME_CLOSED, EventKind.FROZEN, EventKind.BLIND):
        assert not render(Event(kind, 0.0))["title"].startswith(kind.value)


def test_render_test_notification():
    ts = datetime(2026, 9, 15, 12, 0).timestamp()
    message = render(Event(EventKind.TEST, ts, "Bildirimler çalışıyor", notify=True))
    assert message == {
        "title": "🔔 Test bildirimi",
        "body": "Bildirimler çalışıyor · 12:00",
        "url": "/#/events",
        "kind": "test",
        "ts": ts,
    }
