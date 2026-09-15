import json
from pathlib import Path
from types import SimpleNamespace

from pywebpush import WebPushException

from ko_monitor.models import Event, EventKind
from ko_monitor.notifier import WebPushNotifier

NOW = 1_000_000.0
SUB_A = {"endpoint": "https://push/a", "keys": {"p256dh": "x", "auth": "y"}}
SUB_B = {"endpoint": "https://push/b", "keys": {"p256dh": "z", "auth": "w"}}


class FakeStorage:
    def __init__(self, subs):
        self.subs = list(subs)
        self.deleted = []

    def subscriptions(self):
        return list(self.subs)

    def delete_subscription(self, endpoint):
        self.deleted.append(endpoint)
        self.subs = [s for s in self.subs if s["endpoint"] != endpoint]


class FakeSend:
    def __init__(self, outcomes=None):
        self.calls = []
        self.outcomes = list(outcomes or [])

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if outcome is not None:
                raise outcome
        return "ok"


def make(subs, send, sleeps):
    return WebPushNotifier(
        FakeStorage(subs), Path("data/vapid_private.pem"), "mailto:me@example.com",
        max_age_s=300.0, send=send, sleep=sleeps.append, now=lambda: NOW,
    )


def event(ts=NOW):
    return Event(EventKind.DEAD, ts, "Ronark Land", notify=True)


def test_sends_to_every_subscription():
    send, sleeps = FakeSend(), []
    notifier = make([SUB_A, SUB_B], send, sleeps)
    assert notifier.send(event()) is True
    assert [c["subscription_info"]["endpoint"] for c in send.calls] == ["https://push/a", "https://push/b"]
    call = send.calls[0]
    assert json.loads(call["data"])["title"] == "💀 Karakter öldü"
    assert call["vapid_private_key"] == str(Path("data/vapid_private.pem"))
    assert call["vapid_claims"] == {"sub": "mailto:me@example.com"}
    assert call["ttl"] == 300
    assert call["timeout"] == 10
    assert sleeps == []


def test_stale_event_is_dropped():
    send = FakeSend()
    assert make([SUB_A], send, []).send(event(ts=NOW - 301)) is False
    assert send.calls == []


def test_gone_subscription_is_deleted_without_retry():
    gone = WebPushException("gone", response=SimpleNamespace(status_code=410, text="", headers={}))
    send, sleeps = FakeSend([gone]), []
    notifier = make([SUB_A], send, sleeps)
    assert notifier.send(event()) is False
    assert len(send.calls) == 1
    assert notifier._storage.deleted == ["https://push/a"]
    assert sleeps == []


def test_transient_failure_is_retried_three_times():
    boom = WebPushException("boom", response=SimpleNamespace(status_code=500, text="", headers={}))
    send, sleeps = FakeSend([boom, boom, boom]), []
    assert make([SUB_A], send, sleeps).send(event()) is False
    assert len(send.calls) == 3
    assert sleeps == [1, 2]


def test_success_after_one_failure():
    send, sleeps = FakeSend([ConnectionError("net"), None]), []
    assert make([SUB_A], send, sleeps).send(event()) is True
    assert len(send.calls) == 2
    assert sleeps == [1]


def test_no_subscriptions():
    assert make([], FakeSend(), []).send(event()) is False
