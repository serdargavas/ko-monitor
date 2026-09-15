import numpy as np
import pytest
from fastapi.testclient import TestClient

from ko_monitor.api import TRUSTED_HOSTS, create_app
from ko_monitor.models import CaptureStatus, Event, EventKind, Snapshot, State
from ko_monitor.status import AgentStatus, StatusBoard
from ko_monitor.storage import Storage

NOW = 1_800_000_000.0
BROWSER_SUBSCRIPTION = {
    "endpoint": "https://web.push.apple.com/QGx1c2VyLWlk",
    "expirationTime": None,
    "keys": {"p256dh": "BPublicKeyBase64Url", "auth": "AuthSecret"},
}


class FakeSource:
    def latest(self):
        return CaptureStatus.OK, np.zeros((1440, 2560, 3), np.uint8)

    def close(self):
        pass


class FakeNotifier:
    def __init__(self, result=True):
        self.result = result
        self.sent = []

    def send(self, event):
        self.sent.append(event)
        return self.result


def make_web_dir(tmp_path):
    web = tmp_path / "web"
    (web / "js").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>KO</title>", encoding="utf-8")
    (web / "manifest.webmanifest").write_text('{"name": "KO Monitor"}', encoding="utf-8")
    (web / "sw.js").write_text("self.addEventListener('push', () => {});", encoding="utf-8")
    (web / "js" / "app.js").write_text("export {};", encoding="utf-8")
    (web / "styles.css").write_text("body { margin: 0; }", encoding="utf-8")
    return web


class Env:
    def __init__(self, tmp_path, notify_result=True):
        self.storage = Storage(tmp_path / "db.sqlite3")
        self.board = StatusBoard()
        self.notifier = FakeNotifier(notify_result)
        app = create_app(
            self.storage, self.board, FakeSource(), self.notifier, "PUBLICKEY",
            web_dir=make_web_dir(tmp_path), now=lambda: NOW,
            extra_hosts=["testserver"],  # TestClient's default Host header
        )
        self.client = TestClient(app)

    def close(self):
        self.client.close()
        self.storage.close()


@pytest.fixture
def env(tmp_path):
    e = Env(tmp_path)
    yield e
    e.close()


def snapshot(ts, state=State.ALIVE):
    return Snapshot(ts, state, 9718, 9996, "Ronark Land", 1_000_000, 20, 28, ts - 5)


def test_status_before_the_first_tick(env):
    response = env.client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == {"server_time": NOW, **AgentStatus().to_dict()}
    assert response.headers["cache-control"] == "no-store"


def test_status_returns_the_published_status(env):
    env.board.publish(AgentStatus(
        updated_at=NOW - 3, state="dead", process_running=True, capture="ok",
        readings={"hp": 0, "hp_max": 9996, "chat_events": []}, zone_last="Ronark Land",
        money_last=1_000_000, slots_used_last=20, slots_total_last=28, inventory_seen_at=NOW - 60,
    ))
    body = env.client.get("/api/status").json()
    assert body["server_time"] == NOW
    assert (body["updated_at"], body["state"], body["capture"]) == (NOW - 3, "dead", "ok")
    assert body["readings"]["hp"] == 0
    assert (body["money_last"], body["slots_used_last"], body["slots_total_last"]) == (1_000_000, 20, 28)


def test_snapshots_default_to_the_last_24_hours(env):
    env.storage.add_snapshot(snapshot(NOW - 90_000))
    env.storage.add_snapshot(snapshot(NOW - 120, State.DEAD))
    env.storage.add_snapshot(snapshot(NOW - 60))
    body = env.client.get("/api/snapshots").json()
    assert [(s["ts"], s["state"]) for s in body] == [(NOW - 120, "dead"), (NOW - 60, "alive")]
    assert body[0] == {
        "ts": NOW - 120, "state": "dead", "hp": 9718, "hp_max": 9996, "zone": "Ronark Land",
        "money_last": 1_000_000, "slots_used_last": 20, "slots_total_last": 28, "inventory_seen_at": NOW - 125,
    }


def test_snapshots_since(env):
    env.storage.add_snapshot(snapshot(NOW - 90_000))
    env.storage.add_snapshot(snapshot(NOW - 60))
    assert len(env.client.get("/api/snapshots", params={"since": 0}).json()) == 2
    assert env.client.get("/api/snapshots", params={"since": NOW}).json() == []
    assert env.client.get("/api/snapshots", params={"since": "yesterday"}).status_code == 422


def test_events_newest_first_with_limit(env):
    for i, kind in enumerate((EventKind.GAME_STARTED, EventKind.DEAD, EventKind.RECOVERED)):
        env.storage.add_event(Event(kind, NOW - 100 + i, "Ronark Land"))
    body = env.client.get("/api/events", params={"limit": 2}).json()
    assert [e["kind"] for e in body] == ["recovered", "dead"]
    assert len(env.client.get("/api/events").json()) == 3
    assert env.client.get("/api/events", params={"limit": 0}).status_code == 422
    assert env.client.get("/api/events", params={"limit": 501}).status_code == 422


def test_vapid_key(env):
    assert env.client.get("/api/push/vapid-key").json() == {"key": "PUBLICKEY"}


def test_subscribe_stores_the_browser_subscription(env):
    response = env.client.post("/api/push/subscribe", json=BROWSER_SUBSCRIPTION)
    assert response.status_code == 201
    assert response.json() == {"ok": True}
    assert env.storage.subscriptions() == [
        {"endpoint": BROWSER_SUBSCRIPTION["endpoint"], "keys": {"p256dh": "BPublicKeyBase64Url", "auth": "AuthSecret"}}
    ]


@pytest.mark.parametrize(
    "body",
    [
        {**BROWSER_SUBSCRIPTION, "endpoint": "http://insecure.example/push"},
        {"endpoint": "https://web.push.apple.com/x"},
        {**BROWSER_SUBSCRIPTION, "keys": {"p256dh": "", "auth": "a"}},
    ],
)
def test_invalid_subscription_is_rejected(env, body):
    assert env.client.post("/api/push/subscribe", json=body).status_code == 422
    assert env.storage.subscriptions() == []


def test_push_test_sends_a_test_event(env):
    env.client.post("/api/push/subscribe", json=BROWSER_SUBSCRIPTION)
    assert env.client.post("/api/push/test").json() == {"delivered": True, "subscriptions": 1}
    [event] = env.notifier.sent
    assert (event.kind, event.ts, event.notify) == (EventKind.TEST, NOW, True)
    assert event.detail == "Bildirimler çalışıyor"
    assert env.storage.recent_events() == []


def test_push_test_reports_failure(tmp_path):
    e = Env(tmp_path, notify_result=False)
    assert e.client.post("/api/push/test").json() == {"delivered": False, "subscriptions": 0}
    e.close()


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("/", "text/html"),
        ("/index.html", "text/html"),
        ("/manifest.webmanifest", "application/manifest+json"),
        ("/sw.js", "text/javascript"),
        ("/js/app.js", "text/javascript"),
        ("/styles.css", "text/css"),
    ],
)
def test_static_files_have_correct_content_types(env, path, content_type):
    response = env.client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["cache-control"] == "no-cache"


def test_unknown_paths_are_404(env):
    assert env.client.get("/api/nope").status_code == 404
    assert env.client.get("/nope.js").status_code == 404


def test_trusted_hosts_are_localhost_and_the_tailnet():
    assert TRUSTED_HOSTS == ["127.0.0.1", "localhost", "*.ts.net"]


def test_foreign_host_header_is_rejected(env):
    # DNS rebinding: a foreign page resolving its own name to 127.0.0.1 sends its own Host.
    response = env.client.get("/api/status", headers={"host": "rebind.evil.example"})
    assert response.status_code == 400
    assert env.client.get("/", headers={"host": "evil.example"}).status_code == 400


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "pc.tail1234.ts.net"])
def test_local_and_tailnet_hosts_are_allowed(tmp_path, host):
    storage = Storage(tmp_path / "db.sqlite3")
    app = create_app(storage, StatusBoard(), FakeSource(), FakeNotifier(), "K", web_dir=make_web_dir(tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/status", headers={"host": host}).status_code == 200
        assert client.get("/api/status").status_code == 400  # TestClient's "testserver" is not trusted by default
    storage.close()


@pytest.mark.parametrize("path, body", [("/api/push/subscribe", BROWSER_SUBSCRIPTION), ("/api/push/test", None)])
def test_foreign_origin_cannot_use_push_endpoints(env, path, body):
    response = env.client.post(path, json=body, headers={"origin": "https://evil.example"})
    assert response.status_code == 403
    assert env.storage.subscriptions() == [] and env.notifier.sent == []


def test_same_host_origin_can_subscribe(env):
    headers = {"origin": "https://pc.tail1234.ts.net", "host": "pc.tail1234.ts.net"}
    assert env.client.post("/api/push/subscribe", json=BROWSER_SUBSCRIPTION, headers=headers).status_code == 201
    assert env.client.post("/api/push/test", headers=headers).status_code == 200
