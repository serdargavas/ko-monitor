# KO Monitor – Plan 2: API, PWA ve Kurulum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan 1'deki Python ajanının üstüne, iPhone'dan Tailscale üzerinden açılan bir PWA (Durum · Canlı · Olaylar · Ayarlar), bunu besleyen FastAPI API'si (durum, geçmiş, olaylar, WebSocket canlı yayın, Web Push aboneliği) ve Windows'ta otomatik başlatma + kurulum belgesi eklemek.

**Architecture:** Tek süreç: `python -m ko_monitor run` ajan döngüsünü arka plan iş parçacığında, uvicorn/FastAPI sunucusunu ana iş parçacığında çalıştırır; ikisi aynı `Storage`, `WgcCapture` ve `WebPushNotifier` nesnelerini paylaşır. Ajan her tick sonunda değişmez bir `AgentStatus` nesnesini kilitli bir `StatusBoard`'a yayınlar; API yalnızca bu nesneyi okur (monitor'a hiç dokunmaz). PWA derleme adımı olmayan vanilla HTML/CSS/JS ES modülleridir ve FastAPI tarafından `web/` klasöründen statik olarak sunulur.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, websockets, pydantic v2 (FastAPI ile gelir), OpenCV (JPEG kodlama, ikon üretimi), pytest + FastAPI `TestClient` (httpx); tarayıcı tarafı: vanilla JavaScript ES modülleri, Service Worker, Push API, Web App Manifest.

**Spec:** `docs/superpowers/specs/2026-09-15-ko-monitor-design.md`

## Global Constraints

- Salt okuma: oyuna tuş/tıklama göndermek, bellek okumak, paket dinlemek YASAK. Canlı yayın yalnızca ekran görüntüsü gönderir; telefondan oyuna hiçbir komut gitmez.
- Python `>=3.12`; sanal ortam `.venv`. Testler: `.venv\Scripts\python.exe -m pytest -q`.
- Komutlar PowerShell'de, proje kökünden (`C:\Users\Serdar\Desktop\ko-monitor`) çalıştırılır.
- Kod ve kod yorumları İngilizce; kullanıcıya görünen metinler (PWA arayüzü, bildirimler, `docs/setup.md`) Türkçe.
- Zaman damgaları `time.time()` (unix saniye, float).
- Gizli/yerel dosyalar git'e girmez: `config.toml`, `data/`, `logs/`, `.venv/`. Ayrıca `.superpowers/`, `samples/_auto/`, `samples/_review/` asla stage edilmez; `git add` her zaman açık dosya yollarıyla yapılır (`git add .` / `git add -A` YASAK).
- Git kimliği global tanımlı değil; commit komutları `git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit ...` biçimindedir ve mesaj sonunda `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` satırı bulunur.
- **Node.js yok ve kurulmayacak.** PWA derleme adımı olmayan vanilla HTML/CSS/JavaScript ES modülleridir (spec'teki React + Vite + TypeScript + vite-plugin-pwa yerine; Task 5 spec'i günceller). JS test aracı yok: JS dosyaları Python testleriyle yapısal olarak (dosya varlığı, import grafiği, service worker önbellek listesi) ve her görevde elle doğrulama listesiyle kontrol edilir.
- API yalnızca `127.0.0.1`'e bağlanır (sabit, ayarlanamaz); port `config.toml` → `[api] port` (varsayılan `8765`). Kimlik doğrulama yok: erişim kontrolü Tailscale'dir (spec §7).
- API uçları tam olarak: `GET /api/status`, `GET /api/snapshots?since=`, `GET /api/events?limit=`, `WS /api/stream?quality=low|medium|high`, `GET /api/push/vapid-key`, `POST /api/push/subscribe`, `POST /api/push/test`.
- Canlı yayın ön ayarları: `low` 960x540 ~5 fps · `medium` 1280x720 ~10 fps (varsayılan) · `high` 1920x1080 ~20 fps. Kare yalnızca bağlı istemci varken kodlanır; bağlantı kapanınca yayın durur.
- Push payload'u tam olarak `messages.render()` JSON'udur: `title`, `body`, `url`, `kind`, `ts`.
- `run --replay` API başlatmaz.
- Sistem yapılandırmasını değiştiren komutlar (Görev Zamanlayıcı kaydı, `tailscale serve`, hesap açma/oturum açma) bu planın adımlarında **çalıştırılmaz**; yalnızca yazılır/belgelenir, kullanıcı kendisi çalıştırır. Plan hiçbir yerde kimlik bilgisi girmez.

## File Structure

```
ko-monitor/
  pyproject.toml                 # + fastapi, uvicorn, websockets
  config.example.toml            # + [api] port, stream_quality
  scripts/
    make_icons.py                # generates web/icons/*.png with OpenCV (no external assets)
    install-autostart.ps1        # Task Scheduler registration; the USER runs it
  docs/
    setup.md                     # Turkish setup guide (healthchecks.io, ntfy, Tailscale, iPhone, autostart)
  web/                           # PWA, served as static files (no build step)
    index.html                   # app shell: <main id="screen"> + bottom tab bar
    styles.css                   # dark, iPhone-first styles for every screen
    manifest.webmanifest
    sw.js                        # app-shell cache, push, notificationclick
    icons/icon-180.png icon-192.png icon-512.png
    js/
      app.js                     # hash router, service worker registration
      api.js                     # fetch helpers + stream URL
      ui.js                      # el(), labels, time/number formatting, eventItem()
      screens/
        settings.js              # Ayarlar: enable push, test push
        status.js                # Durum: badge, HP bar, inventory, last 5 events (5 s polling)
        events.js                # Olaylar: event list + 24 h state timeline
        live.js                  # Canlı: WebSocket JPEG stream, quality, reconnect, pause when hidden
  src/ko_monitor/
    config.py                    # + ApiConfig, STREAM_QUALITIES
    models.py                    # + EventKind.TEST
    messages.py                  # + TEST title
    status.py                    # AgentStatus (immutable), status_from(), StatusBoard (thread-safe)
    agent.py                     # Agent publishes AgentStatus after every tick (board=...)
    capture.py                   # WgcCapture: session lock + set_stream_fps()
    api.py                       # create_app(): REST endpoints + static web/
    stream.py                    # STREAM_PRESETS, encode_frame(), stream_router() (WS /api/stream)
    runtime.py                   # make_server(), run_with_api(), serve()
    cli.py                       # run: agent thread + API server; ValueError config errors
  tests/
    test_status.py test_api.py test_stream.py test_runtime.py test_web.py test_scripts.py
    (+ additions to test_config.py, test_messages.py, test_agent.py, test_capture.py, test_cli.py)
```

---

### Task 1: Bağımlılıklar, `[api]` ayarları ve thread-safe durum panosu

**Files:**
- Modify: `pyproject.toml` (dependencies)
- Modify: `config.example.toml` (yeni `[api]` bölümü)
- Modify: `src/ko_monitor/config.py` (beş küçük ekleme; dosya baştan yazılmaz)
- Modify: `src/ko_monitor/cli.py` (`main()` içindeki `except` satırı)
- Modify: `src/ko_monitor/models.py` (`EventKind.TEST`)
- Modify: `src/ko_monitor/messages.py` (`TITLES[EventKind.TEST]`)
- Create: `src/ko_monitor/status.py`
- Modify: `src/ko_monitor/agent.py` (üç küçük ekleme; dosya baştan yazılmaz)
- Test: `tests/test_status.py` (yeni), `tests/test_config.py`, `tests/test_messages.py`, `tests/test_agent.py`, `tests/test_cli.py` (eklemeler)

**Interfaces:**
- Consumes (mevcut kod): `Monitor` (`state: State | None`, `last_readings: Readings | None`, `zone_last`, `money_last`, `slots_used_last`, `slots_total_last`, `inventory_seen_at`), `Observation`, `CaptureStatus`, `Readings`, `Agent(cfg, storage, source, detector, monitor, notifier, heartbeat, process_running, now=time.time, monotonic=time.monotonic)`, `load_config(path, base_dir=PROJECT_ROOT)`.
- Produces:
  - `STREAM_QUALITIES: tuple[str, ...] = ("low", "medium", "high")`
  - `ApiConfig(port: int = 8765, stream_quality: str = "medium")` — geçersiz değerde `ValueError`; `Config.api: ApiConfig`
  - `EventKind.TEST = "test"`; `render(Event(EventKind.TEST, ...))["title"] == "🔔 Test bildirimi"`
  - `AgentStatus(updated_at: float | None = None, state: str | None = None, process_running: bool = False, capture: str | None = None, readings: dict | None = None, zone_last: str | None = None, money_last: int | None = None, slots_used_last: int | None = None, slots_total_last: int | None = None, inventory_seen_at: float | None = None)` (frozen) + `to_dict() -> dict`
  - `status_from(monitor: Monitor, ts: float, process_running: bool, capture: CaptureStatus | None) -> AgentStatus` — `readings` is `dataclasses.asdict(monitor.last_readings)` with numpy scalars converted to Python values (new `Readings` fields flow through automatically)
  - `StatusBoard()` with `publish(status: AgentStatus) -> None`, `current() -> AgentStatus` (starts as `AgentStatus()`)
  - `Agent(..., board: StatusBoard | None = None)` (last constructor parameter) — publishes `status_from(monitor, ts, running, observation.capture)` after the events of every `tick()`

- [ ] **Step 1: Bağımlılıkları ekle ve kur**

`pyproject.toml` içinde `dependencies` listesini şu hale getir:
```toml
dependencies = [
  "windows-capture==2.0.1",
  "numpy>=2.0",
  "opencv-python>=4.10",
  "rapidocr==3.9.2",
  "onnxruntime>=1.20",
  "psutil>=7.0",
  "pywebpush==2.5.0",
  "py-vapid==1.9.4",
  "httpx>=0.28",
  "cryptography>=42",
  "fastapi>=0.115",
  "uvicorn>=0.32",
  "websockets>=13",
]
```
(`websockets` gerekli: uvicorn, WebSocket kütüphanesi yoksa `/api/stream` isteklerini reddeder.)

Run: `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
Expected: `Successfully installed ... fastapi-... uvicorn-... websockets-...` (sürüm numaraları farklı olabilir)

Run: `.venv\Scripts\python.exe -c "import fastapi, uvicorn, websockets; from fastapi.testclient import TestClient; print('ok')"`
Expected: `ok`

- [ ] **Step 2: Failing testleri yaz**

`tests/test_config.py` dosyasının import satırlarını şu hale getir ve dosyanın sonuna iki test ekle:
```python
from pathlib import Path

import pytest

from helpers import ROOT
from ko_monitor.config import ApiConfig, load_config
```
```python
def test_api_defaults_and_overrides(tmp_path: Path):
    assert load_config(None).api == ApiConfig(port=8765, stream_quality="medium")
    path = tmp_path / "config.toml"
    path.write_text('[api]\nport = 9000\nstream_quality = "high"\n', encoding="utf-8")
    assert load_config(path).api == ApiConfig(port=9000, stream_quality="high")


@pytest.mark.parametrize("text", ['[api]\nstream_quality = "ultra"\n', "[api]\nport = 0\n", "[api]\nport = 70000\n"])
def test_invalid_api_settings_raise_value_error(tmp_path: Path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)
```

`tests/test_cli.py` içindeki `test_malformed_config_is_a_one_line_error` testinin dekoratörünü şu hale getir (üçüncü durum eklendi, test gövdesi aynı kalır):
```python
@pytest.mark.parametrize(
    "text",
    [
        "[general\nprocess_name = 1\n",
        "[thresholds]\nno_such_threshold = 1\n",
        '[api]\nstream_quality = "ultra"\n',
    ],
)
```

`tests/test_messages.py` sonuna ekle:
```python
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
```

`tests/test_status.py`:
```python
import dataclasses
import json
import threading

import numpy as np

from ko_monitor.config import Thresholds
from ko_monitor.models import CaptureStatus, Readings
from ko_monitor.monitor import Monitor, Observation
from ko_monitor.status import AgentStatus, StatusBoard, status_from


def observed_monitor(readings: Readings) -> Monitor:
    monitor = Monitor(Thresholds())
    monitor.observe(Observation(100.0, True, CaptureStatus.OK, readings))
    return monitor


def test_board_starts_empty():
    status = StatusBoard().current()
    assert status == AgentStatus()
    assert status.updated_at is None and status.state is None and status.readings is None


def test_status_from_monitor_is_plain_json_data():
    readings = Readings(
        hud_visible=True, hp=np.int64(9000), hp_max=9996, zone="Ronark Land",
        chat_events=["inventory_full"], frame_diff=np.float32(5.0),
    )
    status = status_from(observed_monitor(readings), 101.0, True, CaptureStatus.OK)
    assert (status.updated_at, status.state, status.process_running, status.capture) == (101.0, "alive", True, "ok")
    assert status.zone_last == "Ronark Land"
    assert status.readings["hp"] == 9000 and type(status.readings["hp"]) is int
    assert type(status.readings["frame_diff"]) is float
    assert status.readings["chat_events"] == ["inventory_full"]
    json.dumps(status.to_dict())


def test_published_status_does_not_change_when_the_monitor_does():
    readings = Readings(hud_visible=True, hp=9000, hp_max=9996, chat_events=["inventory_full"])
    monitor = observed_monitor(readings)
    status = status_from(monitor, 101.0, True, CaptureStatus.OK)
    readings.hp = 1
    readings.chat_events.append("something_else")
    monitor.zone_last = "Moradon"
    assert status.readings["hp"] == 9000
    assert status.readings["chat_events"] == ["inventory_full"]
    assert status.zone_last is None


def test_new_readings_fields_flow_through():
    @dataclasses.dataclass
    class ExtendedReadings(Readings):
        dialog_text: str | None = None

    monitor = Monitor(Thresholds())
    monitor.state = None
    monitor.last_readings = ExtendedReadings(hud_visible=False, dialog_text="Bağlantı koptu")
    status = status_from(monitor, 5.0, True, CaptureStatus.OK)
    assert status.readings["dialog_text"] == "Bağlantı koptu"
    assert status.state is None


def test_closed_game_has_no_capture_or_readings():
    monitor = Monitor(Thresholds())
    monitor.observe(Observation(1.0, False))
    status = status_from(monitor, 1.0, False, None)
    assert (status.state, status.capture, status.readings, status.process_running) == ("closed", None, None, False)


def test_concurrent_publish_and_read_always_sees_whole_statuses():
    board = StatusBoard()
    errors = []

    def writer():
        for i in range(20_000):
            board.publish(AgentStatus(updated_at=float(i), readings={"hp": i}))

    def reader():
        for _ in range(20_000):
            status = board.current()
            if status.updated_at is not None and status.readings["hp"] != status.updated_at:
                errors.append(status)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert board.current().updated_at == 19_999.0
```

`tests/test_agent.py` import bloğuna `from ko_monitor.status import StatusBoard` ekle ve dosyanın sonuna ekle:
```python
def test_tick_publishes_status_to_the_board(tmp_path):
    board = StatusBoard()
    storage = Storage(tmp_path / "db.sqlite3")
    running = {"value": True}
    agent = Agent(
        Config(data_dir=tmp_path), storage, FakeSource(), FakeDetector(), Monitor(Config().thresholds),
        FakeNotifier(), FakeHeartbeat(), lambda: running["value"], now=lambda: 42.0, board=board,
    )
    agent.tick()
    status = board.current()
    assert (status.updated_at, status.state, status.process_running, status.capture) == (42.0, "alive", True, "ok")
    assert status.readings["hp"] == 9000
    assert status.zone_last == "Ronark Land"

    running["value"] = False
    agent.tick()
    status = board.current()
    assert (status.state, status.process_running, status.capture, status.readings) == ("closed", False, None, None)
    storage.close()


def test_capture_failure_is_published_as_not_found(tmp_path):
    board = StatusBoard()
    source = FlakySource()
    source.fail = True
    storage = Storage(tmp_path / "db.sqlite3")
    agent = Agent(
        Config(data_dir=tmp_path), storage, source, FakeDetector(), Monitor(Config().thresholds),
        FakeNotifier(), FakeHeartbeat(), lambda: True, now=lambda: 7.0, board=board,
    )
    agent.tick()
    assert (board.current().capture, board.current().readings) == ("not_found", None)
    storage.close()
```

- [ ] **Step 3: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_status.py tests/test_config.py tests/test_messages.py tests/test_agent.py tests/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.status'`, `ImportError: cannot import name 'ApiConfig'`, `AttributeError: TEST`, `TypeError: Agent.__init__() got an unexpected keyword argument 'board'`

- [ ] **Step 4: `config.py`, `models.py`, `messages.py`, `cli.py` değişiklikleri**

`src/ko_monitor/config.py` başka bir görevde de değişebildiği için (ör. yeni `Thresholds` alanları) dosyayı baştan yazma; aşağıdaki beş eklemeyi yap. Bağlantı satırları dosyada aynen bulunur.

1) Şu satırın hemen altına
```python
from pathlib import Path
```
ekle:
```python

STREAM_QUALITIES = ("low", "medium", "high")
```

2) `class Config:` tanımının üstündeki `@dataclass(frozen=True)` satırının hemen **önüne** ekle:
```python
@dataclass(frozen=True)
class ApiConfig:
    port: int = 8765
    stream_quality: str = "medium"  # used when a stream client does not ask for a quality

    def __post_init__(self) -> None:
        if not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ValueError(f"api.port must be an integer between 1 and 65535, got {self.port!r}")
        if self.stream_quality not in STREAM_QUALITIES:
            raise ValueError(
                f"api.stream_quality must be one of {', '.join(STREAM_QUALITIES)}, got {self.stream_quality!r}"
            )


```

3) `Config` içinde şu satırın hemen altına
```python
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
```
ekle:
```python
    api: ApiConfig = field(default_factory=ApiConfig)
```

4) `load_config` içindeki `return Config(...)` çağrısında şu satırın hemen altına
```python
        heartbeat=HeartbeatConfig(**raw.get("heartbeat", {})),
```
ekle:
```python
        api=ApiConfig(**raw.get("api", {})),
```

5) `load_config` docstring'indeki satırı
```python
    Raises tomllib.TOMLDecodeError for invalid TOML and TypeError for unknown keys in a section.
```
şu hale getir:
```python
    Raises tomllib.TOMLDecodeError for invalid TOML, TypeError for unknown keys in a section
    and ValueError for invalid [api] values.
```

`src/ko_monitor/models.py` içinde `EventKind`'e son üye olarak ekle:
```python
    INVENTORY_FULL = "inventory_full"
    TEST = "test"  # manual test notification from the PWA; never produced by the monitor
```

`src/ko_monitor/messages.py` içinde `TITLES` sözlüğüne son girdi olarak ekle:
```python
    EventKind.RECOVERED: "✅ Düzeldi",
    EventKind.TEST: "🔔 Test bildirimi",
}
```

`src/ko_monitor/cli.py` → `main()` içindeki satırı:
```python
    except (tomllib.TOMLDecodeError, TypeError) as exc:
```
şu hale getir:
```python
    except (tomllib.TOMLDecodeError, TypeError, ValueError) as exc:
```

`config.example.toml` sonuna ekle:
```toml

[api]
port = 8765                 # the API/PWA listens on 127.0.0.1:<port>; publish it with `tailscale serve --bg <port>`
stream_quality = "medium"   # live view default when the phone does not choose: low | medium | high
```

- [ ] **Step 5: `status.py` yaz**

`src/ko_monitor/status.py`:
```python
"""Immutable agent status shared between the agent loop thread and the API thread."""

from __future__ import annotations

import dataclasses
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ko_monitor.models import CaptureStatus

if TYPE_CHECKING:
    from ko_monitor.monitor import Monitor


@dataclass(frozen=True)
class AgentStatus:
    """What the agent knew after one tick. Built from copies, so other threads can read it freely."""

    updated_at: float | None = None
    state: str | None = None
    process_running: bool = False
    capture: str | None = None
    readings: dict | None = None
    zone_last: str | None = None
    money_last: int | None = None
    slots_used_last: int | None = None
    slots_total_last: int | None = None
    inventory_seen_at: float | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _plain(value):
    """Deep-copies into JSON-friendly Python values (numpy scalars from detectors become int/float)."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, bytes, bool, int, float)) or value is None:
        return value
    if hasattr(value, "item"):
        return value.item()
    return value


def status_from(
    monitor: Monitor, ts: float, process_running: bool, capture: CaptureStatus | None
) -> AgentStatus:
    readings = monitor.last_readings
    return AgentStatus(
        updated_at=ts,
        state=monitor.state.value if monitor.state is not None else None,
        process_running=process_running,
        capture=capture.value if capture is not None else None,
        # asdict() is generic: fields added to Readings later are published without changes here.
        readings=_plain(dataclasses.asdict(readings)) if readings is not None else None,
        zone_last=monitor.zone_last,
        money_last=_plain(monitor.money_last),
        slots_used_last=_plain(monitor.slots_used_last),
        slots_total_last=_plain(monitor.slots_total_last),
        inventory_seen_at=monitor.inventory_seen_at,
    )


class StatusBoard:
    """The agent loop publishes, the API reads. Statuses are immutable; the lock guards the swap."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = AgentStatus()

    def publish(self, status: AgentStatus) -> None:
        with self._lock:
            self._status = status

    def current(self) -> AgentStatus:
        with self._lock:
            return self._status
```

Not: `_plain` içinde `bool` ve `int` kontrolü `hasattr(value, "item")`'dan önce gelir; `np.int64` Python `int` alt sınıfı değildir, bu yüzden `.item()` ile dönüştürülür. `np.float64` Python `float` alt sınıfıdır ve olduğu gibi kalır (JSON'a yazılabilir), `np.float32` ise `.item()` ile `float` olur.

- [ ] **Step 6: `agent.py` — her tick sonunda durumu yayınla**

`agent.py` başka bir görevde de değişebildiği için (ör. olay karesi kaydetme, `incident_dir` parametresi) dosyayı baştan yazma; aşağıdaki üç eklemeyi yap. Bağlantı noktası olarak verilen satırlar dosyada aynen bulunur.

1) Import: şu satırın hemen altına
```python
from ko_monitor.notifier import Notifier, PrintNotifier
```
ekle:
```python
from ko_monitor.status import StatusBoard, status_from
```

2) Kurucu: parametre listesinin **en sonuna** (kapanan `):` satırından hemen önce) ekle:
```python
        board: StatusBoard | None = None,
```
ve gövdede şu satırın hemen altına
```python
        self._monotonic = monotonic
```
ekle:
```python
        self._board = board
```

3) `tick()`: şu iki satırın hemen **önüne**
```python
        t = self._cfg.thresholds
        if running and ts - self._last_snapshot >= t.snapshot_s:
```
ekle (olay döngüsünden sonra, snapshot/heartbeat'ten önce; böylece storage yazımı hata verse bile durum yayınlanmış olur):
```python
        if self._board is not None:
            # Observation.capture is None while the game is closed.
            self._board.publish(status_from(self.monitor, ts, running, observation.capture))
```

Sonuç olarak `tick()`'in ilgili bölümü şöyle görünür (olay döngüsünün gövdesi başka eklemeler içerebilir):
```python
        for event in self.monitor.observe(observation):
            self._handle(event)

        if self._board is not None:
            # Observation.capture is None while the game is closed.
            self._board.publish(status_from(self.monitor, ts, running, observation.capture))

        t = self._cfg.thresholds
        if running and ts - self._last_snapshot >= t.snapshot_s:
```

- [ ] **Step 7: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_status.py tests/test_config.py tests/test_messages.py tests/test_agent.py tests/test_cli.py -q`
Expected: PASS (hepsi)

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: tümü PASS (örneği olmayan kalibrasyon kategorileri SKIPPED)

- [ ] **Step 8: Commit**

```powershell
git add pyproject.toml config.example.toml src/ko_monitor/config.py src/ko_monitor/cli.py src/ko_monitor/models.py src/ko_monitor/messages.py src/ko_monitor/status.py src/ko_monitor/agent.py tests/test_status.py tests/test_config.py tests/test_messages.py tests/test_agent.py tests/test_cli.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: api settings, test notification kind and thread-safe agent status board" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: FastAPI uygulaması — durum, geçmiş, olaylar, push ve statik dosyalar

**Files:**
- Create: `src/ko_monitor/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `StatusBoard.current() -> AgentStatus`, `AgentStatus.to_dict()`, `EventKind.TEST` (Task 1); `Storage.snapshots_since(ts) -> list[Snapshot]`, `Storage.recent_events(limit) -> list[dict]`, `Storage.add_subscription(endpoint, keys, now)`, `Storage.subscriptions() -> list[dict]` (mevcut); `Notifier.send(event) -> bool` (mevcut); `FrameSource` (mevcut; bu görevde yalnızca parametre, Task 3 kullanır); `PROJECT_ROOT` (mevcut).
- Produces:
  - `WEB_DIR: Path = PROJECT_ROOT / "web"`
  - `create_app(storage, board: StatusBoard, source: FrameSource, notifier: Notifier, vapid_public_key: str, *, stream_quality: str = "medium", web_dir: Path = WEB_DIR, now: Callable[[], float] = time.time) -> FastAPI`
  - `GET /api/status` → `{"server_time": float, **AgentStatus.to_dict()}`
  - `GET /api/snapshots?since=<unix s>` → `list[{"ts", "state", "hp", "hp_max", "zone", "money_last", "slots_used_last", "slots_total_last", "inventory_seen_at"}]` eskiden yeniye; `since` yoksa son 24 saat
  - `GET /api/events?limit=<1..500, varsayılan 50>` → `Storage.recent_events` sözlükleri, yeniden eskiye
  - `GET /api/push/vapid-key` → `{"key": str}`
  - `POST /api/push/subscribe` (tarayıcının `PushSubscription.toJSON()` gövdesi) → 201 `{"ok": true}`; geçersizse 422
  - `POST /api/push/test` → `{"delivered": bool, "subscriptions": int}` (olay `events` tablosuna yazılmaz)
  - Statik: `/` → `web/index.html`; `.js` → `text/javascript`, `.webmanifest` → `application/manifest+json`; API yanıtları `Cache-Control: no-store`, statik dosyalar `Cache-Control: no-cache`

- [ ] **Step 1: Failing testleri yaz**

`tests/test_api.py`:
```python
import numpy as np
import pytest
from fastapi.testclient import TestClient

from ko_monitor.api import create_app
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
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.api'`

- [ ] **Step 3: `api.py` yaz**

`src/ko_monitor/api.py`:
```python
"""HTTP API and static PWA files. Listens on 127.0.0.1 only; Tailscale is the access control."""

import dataclasses
import logging
import mimetypes
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ko_monitor.capture import FrameSource
from ko_monitor.config import PROJECT_ROOT
from ko_monitor.models import Event, EventKind
from ko_monitor.notifier import Notifier
from ko_monitor.status import StatusBoard
from ko_monitor.storage import Storage

log = logging.getLogger(__name__)

WEB_DIR = PROJECT_ROOT / "web"
DAY_S = 86400.0

# The Windows registry can map .js to text/plain, which browsers refuse for ES modules,
# and .webmanifest is unknown to Python's defaults.
for _content_type, _extension in (
    ("text/html", ".html"),
    ("text/css", ".css"),
    ("text/javascript", ".js"),
    ("application/manifest+json", ".webmanifest"),
    ("image/png", ".png"),
):
    mimetypes.add_type(_content_type, _extension)


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class SubscriptionIn(BaseModel):
    """PushSubscription.toJSON() from the browser; extra fields (expirationTime) are ignored."""

    endpoint: str = Field(pattern=r"^https://")
    keys: SubscriptionKeys


def create_app(
    storage: Storage,
    board: StatusBoard,
    source: FrameSource,
    notifier: Notifier,
    vapid_public_key: str,
    *,
    stream_quality: str = "medium",
    web_dir: Path = WEB_DIR,
    now: Callable[[], float] = time.time,
) -> FastAPI:
    """source and stream_quality feed the live stream route added in stream.py (Task 3)."""
    app = FastAPI(title="KO Monitor", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def cache_headers(request: Request, call_next):
        response = await call_next(request)
        # API data must always be fresh; static files may be cached but are revalidated.
        is_api = request.url.path.startswith("/api/")
        response.headers["Cache-Control"] = "no-store" if is_api else "no-cache"
        return response

    @app.get("/api/status")
    def get_status():
        return {"server_time": now(), **board.current().to_dict()}

    @app.get("/api/snapshots")
    def get_snapshots(since: float | None = None):
        start = now() - DAY_S if since is None else since
        return [
            {**dataclasses.asdict(s), "state": s.state.value}
            for s in storage.snapshots_since(start)
        ]

    @app.get("/api/events")
    def get_events(limit: int = Query(50, ge=1, le=500)):
        return storage.recent_events(limit=limit)

    @app.get("/api/push/vapid-key")
    def get_vapid_key():
        return {"key": vapid_public_key}

    @app.post("/api/push/subscribe", status_code=201)
    def subscribe(subscription: SubscriptionIn):
        storage.add_subscription(subscription.endpoint, subscription.keys.model_dump(), now())
        log.info("push subscription saved")
        return {"ok": True}

    @app.post("/api/push/test")
    def push_test():
        # Sync endpoint: FastAPI runs it in a worker thread, so push retries do not block the event loop.
        count = len(storage.subscriptions())
        delivered = notifier.send(Event(EventKind.TEST, now(), "Bildirimler çalışıyor", notify=True))
        return {"delivered": delivered, "subscriptions": count}

    # Keep the static mount last: routes registered before it take precedence.
    # check_dir=False lets the API start before web/ exists (Task 5 creates it).
    app.mount("/", StaticFiles(directory=web_dir, html=True, check_dir=False), name="web")
    return app
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py -q`
Expected: PASS (hepsi)

- [ ] **Step 5: Commit**

```powershell
git add src/ko_monitor/api.py tests/test_api.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: fastapi app with status, history, events, push and static files" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Canlı yayın — `WS /api/stream` ve paylaşımlı yakalama

**Files:**
- Modify: `src/ko_monitor/capture.py` (`WgcCapture` sınıfının tamamı aşağıdaki sürümle değişir; dosyanın geri kalanı aynı)
- Create: `src/ko_monitor/stream.py`
- Modify: `src/ko_monitor/api.py` (bir import + `create_app` içinde bir satır)
- Test: `tests/test_stream.py` (yeni), `tests/test_capture.py` (eklemeler)

**Interfaces:**
- Consumes: `create_app(storage, board, source, notifier, vapid_public_key, *, stream_quality, web_dir, now)` (Task 2); `FrameSource.latest() -> tuple[CaptureStatus, np.ndarray | None]` (mevcut); `STREAM_QUALITIES` (Task 1).
- Produces:
  - `WgcCapture(window_title: str, black_threshold: float = 0.95, idle_interval_ms: int = 1000)`; `latest()` ve `close()` artık iki iş parçacığından (ajan döngüsü + yayın) güvenle çağrılabilir; `set_stream_fps(fps: float | None) -> None` — izleyici varken WGC oturumu `1000/fps` ms aralıkla yeniden başlatılır, `None` boşta aralığa döner
  - `StreamPreset(width: int, height: int, fps: float, jpeg_quality: int)`; `STREAM_PRESETS: dict[str, StreamPreset]` (`low`, `medium`, `high`)
  - `encode_frame(frame: np.ndarray, preset: StreamPreset) -> bytes` — en-boy oranını koruyarak ön ayar kutusuna sığdırır (asla büyütmez), JPEG
  - `stream_router(source: FrameSource, default_quality: str) -> APIRouter` — `WS /api/stream?quality=`; ikili mesaj = bir JPEG kare; metin mesajı = `{"status": "<capture status>"}` (kare yokken); bilinmeyen kalite → kabul etmeden 1008 ile kapatır; birden fazla izleyicide en yüksek fps istenir; son izleyici çıkınca `set_stream_fps(None)`

- [ ] **Step 1: Failing testleri yaz**

`tests/test_capture.py` import satırlarını şu hale getir:
```python
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.capture import ReplaySource, WgcCapture, is_black
from ko_monitor.models import CaptureStatus
```
ve dosyanın sonuna ekle:
```python
def test_wgc_restarts_the_session_when_the_stream_rate_changes(monkeypatch):
    monkeypatch.setattr("ko_monitor.capture.find_window", lambda title: 1234)
    monkeypatch.setattr("ko_monitor.capture.is_minimized", lambda hwnd: False)
    clock = FakeClock(0.0)
    monkeypatch.setattr("ko_monitor.capture.time.monotonic", clock)

    cap = WgcCapture("Knight Evolution")
    intervals: list[int] = []
    controls: list[FakeControl] = []
    frame = np.full((4, 4, 3), 200, np.uint8)

    def fake_start():
        intervals.append(cap._session_interval_ms)
        controls.append(FakeControl(finished=False))
        cap._control = controls[-1]
        with cap._lock:
            cap._frame = frame

    monkeypatch.setattr(cap, "_start", fake_start)

    assert cap.latest()[0] == CaptureStatus.OK
    assert intervals == [1000]

    cap.set_stream_fps(10.0)
    assert cap.latest()[0] == CaptureStatus.OK  # restarted at once, not after the backoff
    assert intervals == [1000, 100]
    assert controls[0].is_finished()

    cap.latest()
    assert intervals == [1000, 100]  # same rate: no restart

    cap.set_stream_fps(20.0)
    cap.latest()
    cap.set_stream_fps(None)
    cap.latest()
    assert intervals == [1000, 100, 50, 1000]


def test_wgc_concurrent_latest_waits_for_a_session_start_in_progress(monkeypatch):
    monkeypatch.setattr("ko_monitor.capture.find_window", lambda title: 1234)
    monkeypatch.setattr("ko_monitor.capture.is_minimized", lambda hwnd: False)
    cap = WgcCapture("Knight Evolution")
    frame = np.full((4, 4, 3), 200, np.uint8)
    entered = threading.Event()
    starts = []

    def slow_start():
        starts.append(1)
        entered.set()
        time.sleep(0.2)
        cap._control = FakeControl(finished=False)
        with cap._lock:
            cap._frame = frame

    monkeypatch.setattr(cap, "_start", slow_start)
    first = threading.Thread(target=cap.latest)
    first.start()
    assert entered.wait(2)
    status, got = cap.latest()  # without the session lock this saw no control and reported NOT_FOUND
    first.join()
    assert status == CaptureStatus.OK and got is frame
    assert starts == [1]
```

`tests/test_stream.py`:
```python
import threading
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ko_monitor.api import create_app
from ko_monitor.models import CaptureStatus
from ko_monitor.status import StatusBoard
from ko_monitor.storage import Storage
from ko_monitor.stream import STREAM_PRESETS, StreamPreset, encode_frame

FULL_FRAME = np.full((1440, 2560, 3), 90, np.uint8)


class FakeSource:
    def __init__(self, status=CaptureStatus.OK, frame=FULL_FRAME, error=None):
        self.status = status
        self.frame = frame
        self.error = error
        self.calls = 0
        self.rates = []
        self._lock = threading.Lock()

    def latest(self):
        with self._lock:
            self.calls += 1
        if self.error is not None:
            raise self.error
        return self.status, self.frame

    def set_stream_fps(self, fps):
        self.rates.append(fps)

    def close(self):
        pass


class FakeNotifier:
    def send(self, event):
        return False


@pytest.fixture
def make_client(tmp_path):
    storages = []

    def factory(source, default_quality="medium"):
        storage = Storage(tmp_path / f"db{len(storages)}.sqlite3")
        storages.append(storage)
        app = create_app(
            storage, StatusBoard(), source, FakeNotifier(), "KEY",
            stream_quality=default_quality, web_dir=tmp_path,
        )
        return TestClient(app)

    yield factory
    for storage in storages:
        storage.close()


def decode(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    assert image is not None, "not a JPEG"
    return image


def test_presets_match_the_spec():
    assert STREAM_PRESETS["low"][:3] == (960, 540, 5.0)
    assert STREAM_PRESETS["medium"][:3] == (1280, 720, 10.0)
    assert STREAM_PRESETS["high"][:3] == (1920, 1080, 20.0)


def test_encode_frame_fits_inside_the_preset_without_upscaling():
    preset = StreamPreset(1280, 720, 10.0, 70)
    assert decode(encode_frame(FULL_FRAME, preset)).shape == (720, 1280, 3)
    assert decode(encode_frame(np.zeros((360, 640, 3), np.uint8), preset)).shape == (360, 640, 3)
    assert decode(encode_frame(np.zeros((2000, 2000, 3), np.uint8), preset)).shape == (720, 720, 3)


def test_default_quality_comes_from_the_config(make_client):
    source = FakeSource()
    with make_client(source, default_quality="low") as client:
        with client.websocket_connect("/api/stream") as ws:
            assert decode(ws.receive_bytes()).shape == (540, 960, 3)
    assert source.rates == [5.0, None]


@pytest.mark.parametrize(
    "quality, shape, fps",
    [("low", (540, 960, 3), 5.0), ("medium", (720, 1280, 3), 10.0), ("high", (1080, 1920, 3), 20.0)],
)
def test_quality_selects_size_and_rate(make_client, quality, shape, fps):
    source = FakeSource()
    with make_client(source) as client:
        with client.websocket_connect(f"/api/stream?quality={quality}") as ws:
            assert decode(ws.receive_bytes()).shape == shape
            assert decode(ws.receive_bytes()).shape == shape
    assert source.rates == [fps, None]


def test_missing_frame_sends_the_capture_status(make_client):
    with make_client(FakeSource(CaptureStatus.MINIMIZED, None)) as client:
        with client.websocket_connect("/api/stream") as ws:
            assert ws.receive_json() == {"status": "minimized"}


def test_capture_error_is_reported_as_not_found(make_client):
    with make_client(FakeSource(error=OSError("session died"))) as client:
        with client.websocket_connect("/api/stream") as ws:
            assert ws.receive_json() == {"status": "not_found"}


def test_unknown_quality_is_rejected_without_capturing(make_client):
    source = FakeSource()
    with make_client(source) as client:
        with pytest.raises(WebSocketDisconnect) as info:
            with client.websocket_connect("/api/stream?quality=ultra") as ws:
                ws.receive_bytes()
    assert info.value.code == 1008
    assert source.calls == 0 and source.rates == []


def test_stream_stops_capturing_after_the_client_disconnects(make_client):
    source = FakeSource()
    with make_client(source) as client:
        with client.websocket_connect("/api/stream?quality=high") as ws:
            ws.receive_bytes()
            ws.receive_bytes()
        calls = source.calls
        time.sleep(0.3)  # at 20 fps a still-running sender would capture ~6 more frames
        assert source.calls == calls
    assert source.rates == [20.0, None]


def test_fastest_viewer_sets_the_capture_rate(make_client):
    source = FakeSource()
    with make_client(source) as client:
        with client.websocket_connect("/api/stream?quality=low") as slow:
            slow.receive_bytes()
            with client.websocket_connect("/api/stream?quality=high") as fast:
                fast.receive_bytes()
            slow.receive_bytes()
    assert source.rates == [5.0, 20.0, 5.0, None]
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_stream.py tests/test_capture.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.stream'`; capture testlerinde `AttributeError: 'WgcCapture' object has no attribute 'set_stream_fps'`

- [ ] **Step 3: `WgcCapture`'ı paylaşımlı kullanıma hazırla**

`src/ko_monitor/capture.py` içinde `class WgcCapture:` satırından dosya sonuna kadar olan bölümü şu kodla değiştir (`FrameSource`, `is_black`, `ReplaySource`, `find_window`, `is_minimized` aynı kalır):
```python
class WgcCapture:
    """Windows Graphics Capture session on the game window; keeps only the newest frame.

    Works while the window is covered by other windows; a minimized window yields no frames.
    Shared by the agent loop thread and live stream viewers: session start/stop is serialized.
    """

    def __init__(self, window_title: str, black_threshold: float = 0.95, idle_interval_ms: int = 1000):
        self._title = window_title
        self._black_threshold = black_threshold
        self._lock = threading.Lock()  # guards _frame, written by the capture thread
        self._session_lock = threading.RLock()  # guards the session: start, stop, backoff
        self._frame: np.ndarray | None = None
        self._control = None
        self._retry_at = 0.0
        self._backoff = 1.0
        self._idle_interval_ms = idle_interval_ms
        # A plain int assignment: set_stream_fps() never waits for a slow session start.
        self._wanted_interval_ms = idle_interval_ms
        self._session_interval_ms = idle_interval_ms

    def set_stream_fps(self, fps: float | None) -> None:
        """Live viewers need more than one frame per tick; None returns to the idle rate."""
        if fps:
            self._wanted_interval_ms = max(1, min(self._idle_interval_ms, int(1000 / fps)))
        else:
            self._wanted_interval_ms = self._idle_interval_ms

    def _start(self) -> None:
        from windows_capture import Frame, InternalCaptureControl, WindowsCapture

        cap = WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            minimum_update_interval=self._session_interval_ms,
            window_name=self._title,
        )

        @cap.event
        def on_frame_arrived(frame: Frame, control: InternalCaptureControl):
            bgr = frame.frame_buffer[:, :, :3].copy()  # buffer is BGRA
            with self._lock:
                self._frame = bgr

        @cap.event
        def on_closed():
            log.info("capture session closed")

        self._control = cap.start_free_threaded()
        log.info("capture session started for %r at %d ms", self._title, self._session_interval_ms)

    def latest(self) -> tuple[CaptureStatus, np.ndarray | None]:
        with self._session_lock:
            hwnd = find_window(self._title)
            if not hwnd:
                self.close()
                return CaptureStatus.NOT_FOUND, None
            if is_minimized(hwnd):
                return CaptureStatus.MINIMIZED, None
            wanted = self._wanted_interval_ms
            rate_change = (
                self._control is not None
                and not self._control.is_finished()
                and self._session_interval_ms != wanted
            )
            if rate_change:
                log.info("capture update interval %d ms -> %d ms", self._session_interval_ms, wanted)
                self.close()
                # Same window, only a new rate: restart now and keep the last frame meanwhile.
                self._retry_at = float("-inf")
                self._backoff = 1.0
            if self._control is None or self._control.is_finished():
                now = time.monotonic()
                if now < self._retry_at:
                    return CaptureStatus.NOT_FOUND, None
                # Reserve the next retry slot before attempting, so a session that
                # dies right after starting (protected content, driver error, ...)
                # still backs off instead of retrying every call.
                self._retry_at = now + self._backoff
                self._backoff = min(self._backoff * 2, 30.0)
                self._session_interval_ms = wanted
                if not rate_change:
                    with self._lock:
                        self._frame = None
                try:
                    self._start()
                except Exception:
                    log.exception("capture start failed; retrying in %.0fs", self._backoff)
                    self._control = None
                    return CaptureStatus.NOT_FOUND, None
            with self._lock:
                frame = self._frame
            if frame is None:
                return CaptureStatus.NOT_FOUND, None
            self._backoff = 1.0
            status = CaptureStatus.BLACK if is_black(frame, self._black_threshold) else CaptureStatus.OK
            return status, frame

    def close(self) -> None:
        with self._session_lock:
            if self._control is not None and not self._control.is_finished():
                self._control.stop()
            self._control = None
```

Not: Önceki sürümde `_start()` başında yapılan `self._frame = None` artık `latest()` içinde (yalnızca gerçek yeniden bağlanmada) yapılır; hız değişikliğinde son kare korunur, böylece ajan döngüsü tek bir `NOT_FOUND` görüp donma/kör sayaçlarını sıfırlamaz.

- [ ] **Step 4: `stream.py` yaz**

`src/ko_monitor/stream.py`:
```python
"""Live view: JPEG frames over a WebSocket, captured and encoded only while someone watches."""

import asyncio
import contextlib
import logging
from typing import NamedTuple

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket
from starlette.concurrency import run_in_threadpool

from ko_monitor.capture import FrameSource
from ko_monitor.models import CaptureStatus

log = logging.getLogger(__name__)


class StreamPreset(NamedTuple):
    width: int
    height: int
    fps: float
    jpeg_quality: int


STREAM_PRESETS: dict[str, StreamPreset] = {
    "low": StreamPreset(960, 540, 5.0, 60),
    "medium": StreamPreset(1280, 720, 10.0, 70),
    "high": StreamPreset(1920, 1080, 20.0, 80),
}


def encode_frame(frame: np.ndarray, preset: StreamPreset) -> bytes:
    """Fits the frame inside the preset box (keeping its aspect ratio, never upscaling) as JPEG."""
    height, width = frame.shape[:2]
    scale = min(preset.width / width, preset.height / height, 1.0)
    if scale < 1.0:
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, preset.jpeg_quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buffer.tobytes()


def _grab(source: FrameSource, preset: StreamPreset) -> tuple[CaptureStatus, bytes | None]:
    """Runs in a worker thread: capture and encoding stay off the event loop."""
    try:
        status, frame = source.latest()
    except Exception:
        log.exception("stream capture failed")
        return CaptureStatus.NOT_FOUND, None
    if frame is None:
        return status, None
    return status, encode_frame(frame, preset)


class _StreamDemand:
    """Asks the source for the rate of the fastest connected viewer (None when nobody watches)."""

    def __init__(self, source: FrameSource):
        self._source = source
        self._rates: list[float] = []

    def _apply(self) -> None:
        setter = getattr(self._source, "set_stream_fps", None)
        if setter is not None:
            setter(max(self._rates) if self._rates else None)

    def add(self, fps: float) -> None:
        self._rates.append(fps)
        self._apply()

    def remove(self, fps: float) -> None:
        self._rates.remove(fps)
        self._apply()


async def _send_frames(websocket: WebSocket, source: FrameSource, preset: StreamPreset) -> None:
    loop = asyncio.get_running_loop()
    interval = 1.0 / preset.fps
    while True:
        started = loop.time()
        status, payload = await run_in_threadpool(_grab, source, preset)
        if payload is not None:
            await websocket.send_bytes(payload)
        else:
            await websocket.send_json({"status": status.value})
        await asyncio.sleep(max(0.0, interval - (loop.time() - started)))


async def _wait_for_disconnect(websocket: WebSocket) -> None:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return


def stream_router(source: FrameSource, default_quality: str) -> APIRouter:
    router = APIRouter()
    demand = _StreamDemand(source)

    @router.websocket("/api/stream")
    async def stream(websocket: WebSocket, quality: str | None = None):
        preset = STREAM_PRESETS.get(quality or default_quality)
        if preset is None:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        demand.add(preset.fps)
        log.info("live viewer connected (%s)", quality or default_quality)
        sender = asyncio.create_task(_send_frames(websocket, source, preset))
        receiver = asyncio.create_task(_wait_for_disconnect(websocket))
        try:
            done, _ = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
            if sender in done and not receiver.done():
                # Sending failed while the client is still there: tell it, so it reconnects.
                with contextlib.suppress(Exception):
                    await websocket.close(code=1011)
        finally:
            for task in (sender, receiver):
                task.cancel()
            # Waits for an in-flight capture to finish, so nothing is captured after this handler ends.
            await asyncio.gather(sender, receiver, return_exceptions=True)
            demand.remove(preset.fps)
            log.info("live viewer disconnected")

    return router
```

- [ ] **Step 5: Yayını uygulamaya bağla**

`src/ko_monitor/api.py` içinde import bloğuna ekle:
```python
from ko_monitor.stream import stream_router
```
`create_app` içinde statik mount'tan hemen önce (yorum satırlarının üstüne) ekle:
```python
    app.include_router(stream_router(source, stream_quality))

    # Keep the static mount last: routes registered before it take precedence.
```

- [ ] **Step 6: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_stream.py tests/test_capture.py tests/test_api.py -q`
Expected: PASS (hepsi)

- [ ] **Step 7: Commit**

```powershell
git add src/ko_monitor/capture.py src/ko_monitor/stream.py src/ko_monitor/api.py tests/test_stream.py tests/test_capture.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: websocket live stream with quality presets and shared capture session" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Tek süreç — ajan iş parçacığı + API sunucusu (`run`)

**Files:**
- Create: `src/ko_monitor/runtime.py`
- Modify: `src/ko_monitor/cli.py` (`cmd_run` fonksiyonunun tamamı aşağıdaki sürümle değişir)
- Test: `tests/test_runtime.py` (yeni), `tests/test_cli.py` (eklemeler)

**Interfaces:**
- Consumes: `create_app(...)`, `WEB_DIR` (Task 2, stream Task 3); `StatusBoard`, `Agent(..., board=)` (Task 1); `ApiConfig` / `Config.api` (Task 1); `Agent.run(stop: threading.Event)`, `WebPushNotifier`, `ensure_vapid_key(path) -> Path`, `application_server_key(path) -> str`, `WgcCapture`, `Storage` (mevcut).
- Produces:
  - `API_HOST = "127.0.0.1"`
  - `make_server(app, port: int) -> uvicorn.Server` (host sabit `127.0.0.1`, `log_config=None`, `access_log=False`)
  - `AgentLoopStopped(RuntimeError)`
  - `run_with_api(loop: Callable[[threading.Event], None], server, stop: threading.Event, join_timeout_s: float = 15.0) -> None` — döngü `agent-loop` adlı iş parçacığında, `server.run()` çağıranın iş parçacığında; sunucu dönünce/istisna atınca `stop` set edilir ve döngü beklenir; döngü beklenmedik biterse `server.should_exit = True` ve sonunda `AgentLoopStopped`
  - `serve(agent, storage, source, notifier, board, cfg: Config, vapid_public_key: str, *, server_factory=make_server, web_dir: Path = WEB_DIR) -> None` — bitince `source.close()` ve `storage.close()` (döngü durduktan sonra)
  - CLI `run` (canlı): API + ajan; Ctrl+C → çıkış kodu 0; `run --replay` API başlatmaz

- [ ] **Step 1: Failing testleri yaz**

`tests/test_runtime.py`:
```python
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ko_monitor.config import ApiConfig, Config
from ko_monitor.runtime import API_HOST, AgentLoopStopped, make_server, run_with_api, serve
from ko_monitor.status import AgentStatus, StatusBoard


class FakeAgent:
    def __init__(self, board):
        self.board = board
        self.started = threading.Event()
        self.stopped = threading.Event()
        self.thread_name = None

    def run(self, stop):
        self.thread_name = threading.current_thread().name
        self.board.publish(AgentStatus(updated_at=1.0, state="alive", process_running=True, capture="ok"))
        self.started.set()
        stop.wait()
        self.stopped.set()


class Closable:
    """Stands in for Storage and WgcCapture; records whether the loop had stopped before close()."""

    def __init__(self, agent):
        self.agent = agent
        self.closed = False
        self.loop_stopped_at_close = None

    def close(self):
        self.loop_stopped_at_close = self.agent.stopped.is_set()
        self.closed = True


class FakeNotifier:
    def send(self, event):
        return False


class FakeServer:
    def __init__(self, app, port, action):
        self.app = app
        self.port = port
        self.action = action
        self.should_exit = False
        self.result = None

    def run(self):
        self.result = self.action(self)


def run_serve(tmp_path, action, port=9123):
    board = StatusBoard()
    agent = FakeAgent(board)
    storage, source = Closable(agent), Closable(agent)
    servers = []

    def factory(app, port):
        servers.append(FakeServer(app, port, action(agent)))
        return servers[-1]

    cfg = Config(api=ApiConfig(port=port))
    serve(agent, storage, source, FakeNotifier(), board, cfg, "KEY", server_factory=factory, web_dir=tmp_path)
    return dict(agent=agent, storage=storage, source=source, servers=servers)


def test_api_reads_the_status_published_by_the_loop_thread(tmp_path):
    def action(agent):
        def run(server):
            assert agent.started.wait(5)
            with TestClient(server.app) as client:
                body = client.get("/api/status").json()
            assert not agent.stopped.is_set()  # the loop keeps running while the server serves
            return body
        return run

    parts = run_serve(tmp_path, action)
    [server] = parts["servers"]
    assert server.port == 9123
    assert (server.result["state"], server.result["updated_at"]) == ("alive", 1.0)
    assert parts["agent"].thread_name == "agent-loop"
    assert parts["agent"].stopped.is_set()
    for resource in (parts["storage"], parts["source"]):
        assert resource.closed and resource.loop_stopped_at_close


def test_ctrl_c_stops_the_loop_and_closes_resources(tmp_path):
    board = StatusBoard()
    agent = FakeAgent(board)
    storage, source = Closable(agent), Closable(agent)

    def factory(app, port):
        def interrupted(server):
            assert agent.started.wait(5)
            raise KeyboardInterrupt
        return FakeServer(app, port, interrupted)

    with pytest.raises(KeyboardInterrupt):
        serve(agent, storage, source, FakeNotifier(), board, Config(), "KEY", server_factory=factory, web_dir=tmp_path)
    assert agent.stopped.is_set()
    assert storage.closed and source.closed and storage.loop_stopped_at_close


def test_normal_server_exit_does_not_raise():
    stopped = threading.Event()

    def loop(stop):
        stop.wait()
        stopped.set()

    class QuickServer:
        should_exit = False

        def run(self):
            time.sleep(0.05)

    stop = threading.Event()
    run_with_api(loop, QuickServer(), stop)
    assert stop.is_set() and stopped.is_set()


def test_loop_crash_stops_the_server_and_raises():
    class WaitingServer:
        should_exit = False

        def run(self):
            deadline = time.monotonic() + 5
            while not self.should_exit and time.monotonic() < deadline:
                time.sleep(0.01)

    def crashing_loop(stop):
        raise RuntimeError("boom")

    server = WaitingServer()
    with pytest.raises(AgentLoopStopped):
        run_with_api(crashing_loop, server, threading.Event())
    assert server.should_exit is True


def test_make_server_binds_localhost_only():
    server = make_server(FastAPI(), 8765)
    assert API_HOST == "127.0.0.1"
    assert (server.config.host, server.config.port, server.config.access_log) == ("127.0.0.1", 8765, False)
```

`tests/test_cli.py` sonuna ekle:
```python
def write_run_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(
        '[general]\ndata_dir = "data"\nlog_dir = "logs"\n'
        f'calibration_path = "{(ROOT / "calibration.json").as_posix()}"\n'
        "[api]\nport = 9123\n",
        encoding="utf-8",
    )
    return path


class FakeCapture:
    def __init__(self, window_title, black_threshold=0.95):
        self.window_title = window_title

    def latest(self):
        raise AssertionError("capture is not used in this test")

    def close(self):
        pass


def patch_heavy_run_parts(monkeypatch):
    """No OCR model, no window capture, no log files: only the wiring in cmd_run is exercised."""
    import ko_monitor.detectors as detectors_module
    import ko_monitor.logging_setup as logging_setup
    import ko_monitor.ocr as ocr_module

    monkeypatch.setattr(logging_setup, "setup_logging", lambda log_dir: None)
    monkeypatch.setattr(ocr_module, "Ocr", lambda min_score=0.0: object())
    monkeypatch.setattr(detectors_module, "Detector", lambda calib, ocr: object())
    monkeypatch.setattr("ko_monitor.cli.WgcCapture", FakeCapture)


def test_live_run_shares_storage_capture_notifier_and_board_with_the_api(tmp_path: Path, monkeypatch):
    import ko_monitor.runtime as runtime

    patch_heavy_run_parts(monkeypatch)
    seen = {}

    def fake_serve(agent, storage, source, notifier, board, cfg, vapid_public_key, **kwargs):
        seen.update(agent=agent, storage=storage, source=source, notifier=notifier, board=board, cfg=cfg, key=vapid_public_key)

    monkeypatch.setattr(runtime, "serve", fake_serve)
    assert main(["--config", str(write_run_config(tmp_path)), "run"]) == 0

    agent = seen["agent"]
    assert agent._storage is seen["storage"]
    assert agent._source is seen["source"]
    assert agent._notifier is seen["notifier"]
    assert agent._board is seen["board"]
    assert isinstance(seen["source"], FakeCapture) and seen["source"].window_title == "Knight Evolution"
    assert seen["cfg"].api.port == 9123
    assert len(seen["key"]) == 87
    assert (tmp_path / "data" / "vapid_private.pem").exists()
    seen["storage"].close()


def test_ctrl_c_ends_the_live_run_with_exit_code_0(tmp_path: Path, monkeypatch):
    import ko_monitor.runtime as runtime

    patch_heavy_run_parts(monkeypatch)
    storages = []

    def interrupted_serve(agent, storage, *args, **kwargs):
        storages.append(storage)
        raise KeyboardInterrupt

    monkeypatch.setattr(runtime, "serve", interrupted_serve)
    assert main(["--config", str(write_run_config(tmp_path)), "run"]) == 0
    storages[0].close()


def test_replay_run_does_not_start_the_api(tmp_path: Path, monkeypatch, capsys):
    import ko_monitor.agent as agent_module
    import ko_monitor.runtime as runtime

    patch_heavy_run_parts(monkeypatch)
    monkeypatch.setattr(runtime, "serve", lambda *args, **kwargs: pytest.fail("replay must not start the API"))
    monkeypatch.setattr(
        agent_module, "run_replay",
        lambda cfg, folder, detector, storage: [{"kind": "game_started", "detail": ""}],
    )
    assert main(["--config", str(write_run_config(tmp_path)), "run", "--replay", str(tmp_path)]) == 0
    assert "game_started" in capsys.readouterr().out
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runtime.py tests/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.runtime'`

- [ ] **Step 3: `runtime.py` yaz**

`src/ko_monitor/runtime.py`:
```python
"""Single process: the agent loop runs in a background thread, the API server in the main thread."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

import uvicorn

from ko_monitor.api import WEB_DIR, create_app
from ko_monitor.config import Config

log = logging.getLogger(__name__)

API_HOST = "127.0.0.1"  # never reachable from the LAN; `tailscale serve` publishes it
LOOP_JOIN_TIMEOUT_S = 15.0


class AgentLoopStopped(RuntimeError):
    """The agent loop ended while the server was still supposed to run."""


def make_server(app, port: int) -> uvicorn.Server:
    # log_config=None keeps our rotating log setup; access logs would flood it (status polling every 5 s).
    config = uvicorn.Config(app, host=API_HOST, port=port, log_config=None, access_log=False)
    return uvicorn.Server(config)


def run_with_api(
    loop: Callable[[threading.Event], None],
    server,
    stop: threading.Event,
    join_timeout_s: float = LOOP_JOIN_TIMEOUT_S,
) -> None:
    """Runs server.run() in the calling thread; stops and joins the loop however the server ends."""
    loop_failed = threading.Event()

    def guarded_loop() -> None:
        try:
            loop(stop)
        except BaseException:
            log.exception("agent loop crashed")
        finally:
            if not stop.is_set():
                loop_failed.set()
                log.error("agent loop ended unexpectedly; stopping the API server")
                server.should_exit = True

    thread = threading.Thread(target=guarded_loop, name="agent-loop", daemon=True)
    thread.start()
    try:
        server.run()
    finally:
        stop.set()
        thread.join(join_timeout_s)
        if thread.is_alive():
            log.warning("agent loop did not stop within %.0f s", join_timeout_s)
    if loop_failed.is_set():
        # Non-zero exit, so Task Scheduler restarts the whole process.
        raise AgentLoopStopped("agent loop stopped unexpectedly")


def serve(
    agent,
    storage,
    source,
    notifier,
    board,
    cfg: Config,
    vapid_public_key: str,
    *,
    server_factory: Callable = make_server,
    web_dir: Path = WEB_DIR,
) -> None:
    app = create_app(
        storage, board, source, notifier, vapid_public_key,
        stream_quality=cfg.api.stream_quality, web_dir=web_dir,
    )
    server = server_factory(app, cfg.api.port)
    log.info("API on http://%s:%d (publish with: tailscale serve --bg %d)", API_HOST, cfg.api.port, cfg.api.port)
    try:
        run_with_api(agent.run, server, threading.Event())
    finally:
        # Only after the loop has stopped: it writes to storage and reads from the capture.
        source.close()
        storage.close()
```

- [ ] **Step 4: `cmd_run`'ı güncelle**

`src/ko_monitor/cli.py` içindeki `cmd_run` fonksiyonunun tamamını şu kodla değiştir. Önce `git log -p -1 -- src/ko_monitor/cli.py` ve `git diff src/ko_monitor/cli.py` ile `cmd_run`'ın Plan 1 sonrası hâlinden farklı olup olmadığına bak; başka bir değişiklik eklenmişse onu da aşağıdaki sürüme taşı (bu görevin farkı yalnızca: `StatusBoard` oluşturma, `vapid_path` + `application_server_key`, `board=board`, `agent.run` yerine `runtime.serve(...)`).
```python
def cmd_run(args: argparse.Namespace, cfg: Config) -> int:
    from ko_monitor import runtime
    from ko_monitor.agent import Agent, run_replay
    from ko_monitor.detectors import Detector
    from ko_monitor.heartbeat import Heartbeat
    from ko_monitor.logging_setup import setup_logging
    from ko_monitor.monitor import Monitor
    from ko_monitor.notifier import WebPushNotifier
    from ko_monitor.ocr import Ocr
    from ko_monitor.process_watch import is_process_running
    from ko_monitor.status import StatusBoard
    from ko_monitor.storage import Storage
    from ko_monitor.vapid import application_server_key, ensure_vapid_key

    setup_logging(cfg.log_dir)
    if not args.replay:
        for warning in run_config_warnings(cfg, args.config):
            log.warning(warning)
    calib = load_calibration(cfg.calibration_path)
    detector = Detector(calib, Ocr(calib.ocr_min_score))

    if args.replay:
        # Offline check of recorded frames: no API, no push, no heartbeat.
        db_path = cfg.data_dir / "replay.sqlite3"
        db_path.unlink(missing_ok=True)
        storage = Storage(db_path)
        try:
            for event in run_replay(cfg, args.replay, detector, storage):
                print(f"{event['kind']:<15} {event['detail']}")
        finally:
            storage.close()
        return 0

    board = StatusBoard()
    storage = Storage(cfg.data_dir / "ko_monitor.sqlite3")
    vapid_path = ensure_vapid_key(cfg.data_dir / "vapid_private.pem")
    notifier = WebPushNotifier(storage, vapid_path, cfg.push.contact, cfg.push.max_age_s)
    source = WgcCapture(cfg.window_title, calib.black_threshold)
    agent = Agent(
        cfg, storage, source, detector, Monitor(cfg.thresholds), notifier,
        Heartbeat(cfg.heartbeat.ping_url, cfg.heartbeat.api_key),
        lambda: is_process_running(cfg.process_name),
        board=board,
    )
    try:
        # One process: agent loop thread + API server (same storage, capture and notifier).
        runtime.serve(agent, storage, source, notifier, board, cfg, application_server_key(vapid_path))
    except KeyboardInterrupt:
        log.info("stopped by user")
    return 0
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runtime.py tests/test_cli.py -q`
Expected: PASS (hepsi)

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: tümü PASS

- [ ] **Step 6: Elle duman testi (oyun kapalı olabilir)**

1. Ayrı bir PowerShell penceresinde: `.venv\Scripts\python.exe -m ko_monitor run`
   Expected log: `agent started` ve `API on http://127.0.0.1:8765 ...`, ardından uvicorn `Uvicorn running on http://127.0.0.1:8765`.
2. Bu pencerede: `Invoke-RestMethod http://127.0.0.1:8765/api/status`
   Expected: `server_time`, `state` (oyun kapalıysa `closed`), `process_running` alanları olan bir nesne; `updated_at` birkaç saniye içinde dolar.
3. `netstat -ano | Select-String ":8765"`
   Expected: yalnızca `127.0.0.1:8765 ... LISTENING` (`0.0.0.0:8765` YOK).
4. İlk penceredeki süreçte Ctrl+C.
   Expected: `agent stopped` logu, süreç birkaç saniye içinde kapanır.

- [ ] **Step 7: Commit**

```powershell
git add src/ko_monitor/runtime.py src/ko_monitor/cli.py tests/test_runtime.py tests/test_cli.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: run the agent loop and the api server in one process" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: PWA kabuğu — manifest, ikonlar, service worker, yönlendirici ve Ayarlar ekranı

**Files:**
- Create: `scripts/make_icons.py`, `web/icons/icon-180.png`, `web/icons/icon-192.png`, `web/icons/icon-512.png` (script üretir)
- Create: `web/index.html`, `web/styles.css`, `web/manifest.webmanifest`, `web/sw.js`
- Create: `web/js/app.js`, `web/js/api.js`, `web/js/ui.js`, `web/js/screens/settings.js`
- Modify: `docs/superpowers/specs/2026-09-15-ko-monitor-design.md` (§2 ve §3 tablo satırları: React → vanilla JS sapması)
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: HTTP uçları (Task 2): `GET /api/status`, `GET /api/events?limit=`, `GET /api/snapshots?since=`, `GET /api/push/vapid-key` → `{"key"}`, `POST /api/push/subscribe`, `POST /api/push/test` → `{"delivered", "subscriptions"}`; `WS /api/stream?quality=` (Task 3); push payload `{"title", "body", "url", "kind", "ts"}` (`messages.render`); `State` ve `EventKind` değerleri (mevcut + `test`).
- Produces (sonraki JS görevleri bunları kullanır):
  - Ekran modülü sözleşmesi: `export default { title: string, mount(root: HTMLElement): (() => void) | null }` — `mount` ekranı `root` içine çizer, dönen fonksiyon ekrandan çıkarken zamanlayıcıları/dinleyicileri/soketleri kapatır.
  - `web/js/app.js`: `const SCREENS = { ... };` — anahtar = hash rotası (`#/status`, `#/live`, `#/events`, `#/settings`); ilk anahtar varsayılan rota. Service worker'dan `{type: "navigate", url}` mesajı gelince `location.hash` değişir.
  - `web/js/api.js`: `ApiError`, `getStatus()`, `getEvents(limit = 50)`, `getSnapshots(since)`, `getVapidKey()`, `subscribePush(subscriptionJson)`, `sendTestPush()`, `streamUrl(quality: string | null) -> string`
  - `web/js/ui.js`: `el(tag, attrs = {}, ...children)`, `STATE_LABELS`, `EVENT_LABELS`, `stateLabel(state) -> {text, tone}`, `eventLabel(kind) -> string`, `agoText(seconds) -> string`, `clockText(ts) -> string`, `dateTimeText(ts) -> string`, `numberText(value) -> string`, `eventItem(event) -> HTMLLIElement`
  - `web/sw.js`: `const CACHE = "ko-monitor-v1";` ve `const SHELL = [...]` (her `web/js/**/*.js` dosyası listede olmalı — test zorlar)
  - CSS sınıfları (sonraki ekranlar yeni CSS yazmaz): `card row meta note ok warn bad off badge hpbar kv event-list event-kind buttons primary active timeline seg timeline-axis legend dot state-<state> state-none live-mode live-header quality live-stage live-frame live-overlay`
  - `scripts/make_icons.py`: `BACKGROUND: tuple[int, int, int]`, `SIZES = (180, 192, 512)`, `render_icon(size: int) -> np.ndarray`, `main(out_dir: Path = ICON_DIR) -> list[Path]`

- [ ] **Step 1: Failing testleri yaz**

`tests/test_web.py`:
```python
import importlib.util
import json
import re

import cv2
import pytest
from fastapi.testclient import TestClient

from helpers import ROOT
from ko_monitor.api import WEB_DIR, create_app
from ko_monitor.models import EventKind, State
from ko_monitor.status import StatusBoard

JS_FILES = sorted((WEB_DIR / "js").rglob("*.js"))
IMPORT = re.compile(r"""(?:import|export)\s[^'"]*?from\s+["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)""")


class NullSource:
    def latest(self):
        raise AssertionError("not used")

    def close(self):
        pass


class NullNotifier:
    def send(self, event):
        return False


@pytest.fixture(scope="module")
def client():
    app = create_app(object(), StatusBoard(), NullSource(), NullNotifier(), "KEY")
    with TestClient(app) as c:
        yield c


def read(relative: str) -> str:
    return (WEB_DIR / relative).read_text(encoding="utf-8")


def sw_shell() -> list[str]:
    block = re.search(r"const SHELL = \[(.*?)\];", read("sw.js"), re.S).group(1)
    return re.findall(r'"([^"]+)"', block)


def registered_screens() -> list[str]:
    block = re.search(r"const SCREENS = \{([^}]*)\};", read("js/app.js")).group(1)
    return [name.strip() for name in block.split(",") if name.strip()]


def tab_routes() -> list[str]:
    return re.findall(r'data-route="([a-z]+)"', read("index.html"))


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("/", "text/html"),
        ("/manifest.webmanifest", "application/manifest+json"),
        ("/sw.js", "text/javascript"),
        ("/styles.css", "text/css"),
        ("/js/app.js", "text/javascript"),
        ("/icons/icon-180.png", "image/png"),
    ],
)
def test_real_web_files_are_served(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


def test_manifest_is_installable():
    manifest = json.loads(read("manifest.webmanifest"))
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "/"
    assert manifest["start_url"].startswith("/")
    assert {"192x192", "512x512"} <= {icon["sizes"] for icon in manifest["icons"]}
    for icon in manifest["icons"]:
        width, height = map(int, icon["sizes"].split("x"))
        image = cv2.imread(str(WEB_DIR / icon["src"].lstrip("/")))
        assert image is not None and image.shape[:2] == (height, width), icon["src"]


def test_index_links_manifest_apple_icon_and_app_module():
    html = read("index.html")
    assert '<html lang="tr">' in html
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert '<link rel="apple-touch-icon" href="/icons/icon-180.png">' in html
    assert '<script type="module" src="/js/app.js"></script>' in html
    assert tab_routes() == ["status", "live", "events", "settings"]
    assert cv2.imread(str(WEB_DIR / "icons" / "icon-180.png")).shape[:2] == (180, 180)


@pytest.mark.parametrize("js_file", JS_FILES, ids=lambda p: p.relative_to(WEB_DIR).as_posix())
def test_relative_imports_resolve(js_file):
    for match in IMPORT.finditer(js_file.read_text(encoding="utf-8")):
        target = match.group(1) or match.group(2)
        assert target.startswith("."), f"{target}: no bundler, only relative imports work"
        assert (js_file.parent / target).resolve().is_file(), f"{js_file.name} imports missing {target}"


def test_service_worker_shell_lists_existing_files_and_every_module():
    shell = sw_shell()
    for entry in shell:
        assert (WEB_DIR / ("index.html" if entry == "/" else entry.lstrip("/"))).is_file(), entry
    for js_file in JS_FILES:
        assert "/" + js_file.relative_to(WEB_DIR).as_posix() in shell


def test_service_worker_shows_the_render_payload_and_opens_its_url():
    text = read("sw.js")
    for needle in (
        'addEventListener("push"', 'addEventListener("notificationclick"', "showNotification(",
        "message.title", "message.body", "message.url", "message.kind", "message.ts",
    ):
        assert needle in text, needle


def test_every_registered_screen_has_a_tab_and_a_module():
    screens = registered_screens()
    assert "settings" in screens
    assert set(screens) <= set(tab_routes())
    for name in screens:
        assert (WEB_DIR / "js" / "screens" / f"{name}.js").is_file()


def test_ui_labels_cover_every_state_and_event_kind():
    text = read("js/ui.js")
    for value in [s.value for s in State] + [k.value for k in EventKind]:
        assert re.search(rf"\b{value}:", text), value


def test_icon_script_draws_opaque_square_icons(tmp_path):
    spec = importlib.util.spec_from_file_location("make_icons", ROOT / "scripts" / "make_icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    icon = module.render_icon(64)
    assert icon.shape == (64, 64, 3)
    assert tuple(int(v) for v in icon[0, 0]) == module.BACKGROUND
    written = module.main(tmp_path)
    assert [p.name for p in written] == ["icon-180.png", "icon-192.png", "icon-512.png"]
    assert cv2.imread(str(written[2])).shape == (512, 512, 3)
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_web.py -q`
Expected: FAIL — `FileNotFoundError` (`web/manifest.webmanifest`, `web/index.html`, `web/sw.js`, `scripts/make_icons.py` yok); `test_relative_imports_resolve` "empty parameter set" ile SKIPPED

- [ ] **Step 3: İkon script'ini yaz ve ikonları üret**

`scripts/make_icons.py`:
```python
"""Generates the PWA icons in web/icons with OpenCV, so the repo needs no external image assets.

Run from the project root: .venv\\Scripts\\python.exe scripts\\make_icons.py
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "web" / "icons"
SIZES = (180, 192, 512)
BACKGROUND = (21, 17, 15)  # BGR of #0f1115, the app background
RING = (111, 191, 63)  # BGR of #3fbf6f, the "alive" green
PULSE = (240, 234, 232)  # BGR of #e8eaf0, the text color


def render_icon(size: int) -> np.ndarray:
    """Opaque square icon (iOS ignores transparency): a green ring with a heartbeat line."""
    scale = 4  # draw large, then downsample for smooth edges
    big = size * scale
    image = np.full((big, big, 3), BACKGROUND, np.uint8)
    cv2.circle(image, (big // 2, big // 2), int(big * 0.36), RING, int(big * 0.06), cv2.LINE_AA)
    pulse = np.array(
        [[0.20, 0.52], [0.38, 0.52], [0.45, 0.33], [0.55, 0.70], [0.62, 0.52], [0.80, 0.52]]
    ) * big
    cv2.polylines(image, [pulse.astype(np.int32)], False, PULSE, int(big * 0.045), cv2.LINE_AA)
    return cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA)


def main(out_dir: Path = ICON_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for size in SIZES:
        path = out_dir / f"icon-{size}.png"
        if not cv2.imwrite(str(path), render_icon(size)):
            raise SystemExit(f"could not write {path}")
        written.append(path)
    return written


if __name__ == "__main__":
    for icon_path in main():
        print(icon_path)
```

Run: `.venv\Scripts\python.exe scripts\make_icons.py`
Expected: üç satır — `...\web\icons\icon-180.png`, `...\icon-192.png`, `...\icon-512.png`

- [ ] **Step 4: Sayfa kabuğu, manifest ve stiller**

`web/index.html`:
```html
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0f1115">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="KO Monitor">
  <title>KO Monitor</title>
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="apple-touch-icon" href="/icons/icon-180.png">
  <link rel="icon" type="image/png" href="/icons/icon-192.png">
  <link rel="stylesheet" href="/styles.css">
  <script type="module" src="/js/app.js"></script>
</head>
<body>
  <main id="screen"></main>
  <nav class="tabs">
    <a href="#/status" data-route="status">Durum</a>
    <a href="#/live" data-route="live">Canlı</a>
    <a href="#/events" data-route="events">Olaylar</a>
    <a href="#/settings" data-route="settings">Ayarlar</a>
  </nav>
</body>
</html>
```

`web/manifest.webmanifest`:
```json
{
  "name": "KO Monitor",
  "short_name": "KO Monitor",
  "description": "Knight Online izleme: durum, canlı görüntü ve bildirimler",
  "lang": "tr",
  "start_url": "/#/status",
  "scope": "/",
  "display": "standalone",
  "orientation": "any",
  "background_color": "#0f1115",
  "theme_color": "#0f1115",
  "icons": [
    {"src": "/icons/icon-180.png", "sizes": "180x180", "type": "image/png"},
    {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}
  ]
}
```

`web/styles.css`:
```css
:root {
  color-scheme: dark;
  --bg: #0f1115;
  --card: #181b22;
  --line: #2a2f3a;
  --text: #e8eaf0;
  --muted: #9aa3b2;
  --ok: #3fbf6f;
  --warn: #e0a526;
  --bad: #e5484d;
  --off: #6b7280;
  --accent: #4f8cff;
  --tabbar-h: 56px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--text); }
body { min-height: 100vh; -webkit-text-size-adjust: 100%; }
[hidden] { display: none !important; }

#screen {
  max-width: 720px;
  margin: 0 auto;
  padding:
    calc(env(safe-area-inset-top) + 12px)
    calc(env(safe-area-inset-right) + 16px)
    calc(env(safe-area-inset-bottom) + var(--tabbar-h) + 16px)
    calc(env(safe-area-inset-left) + 16px);
}

h1 { font-size: 1.6rem; margin: 4px 0 12px; }
h2 { font-size: 1rem; margin: 0 0 10px; color: var(--muted); font-weight: 600; }

.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px; margin-bottom: 12px; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.meta { color: var(--muted); font-size: 0.9rem; margin: 6px 0; }
.note { font-size: 0.95rem; margin: 8px 0; }
.ok { color: var(--ok); }
.warn { color: var(--warn); }
.bad { color: var(--bad); }
.off { color: var(--off); }

.badge { display: inline-block; padding: 4px 12px; border-radius: 999px; font-weight: 700; color: #0b0d11; background: var(--off); }
.badge.ok { background: var(--ok); color: #0b0d11; }
.badge.warn { background: var(--warn); color: #0b0d11; }
.badge.bad { background: var(--bad); color: #fff; }
.badge.off { background: var(--off); color: #fff; }

.hpbar { height: 12px; background: #262a33; border-radius: 6px; overflow: hidden; margin-top: 6px; }
.hpbar > span { display: block; height: 100%; background: linear-gradient(90deg, #c2352f, #e5484d); }

.kv { display: grid; grid-template-columns: auto 1fr; gap: 6px 16px; margin: 0; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }

.event-list { list-style: none; margin: 0; padding: 0; }
.event-list li { display: flex; flex-direction: column; gap: 2px; padding: 10px 0; border-top: 1px solid var(--line); }
.event-list li:first-child { border-top: 0; }
.event-kind { font-weight: 600; }

button {
  font: inherit; color: var(--text); background: #232834; border: 1px solid var(--line);
  border-radius: 10px; padding: 10px 14px; min-height: 44px; cursor: pointer;
}
button.primary, button.active { background: var(--accent); border-color: var(--accent); color: #fff; }
button:disabled { opacity: 0.5; cursor: default; }
.buttons { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }

nav.tabs {
  position: fixed; left: 0; right: 0; bottom: 0; display: flex;
  background: rgba(15, 17, 21, 0.96); border-top: 1px solid var(--line);
  padding-bottom: env(safe-area-inset-bottom);
  -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px);
}
nav.tabs a {
  flex: 1; height: var(--tabbar-h); display: flex; align-items: center; justify-content: center;
  color: var(--muted); text-decoration: none; font-weight: 600;
}
nav.tabs a.active { color: var(--accent); }

.timeline { position: relative; height: 28px; background: #232834; border-radius: 6px; overflow: hidden; }
.timeline .seg { position: absolute; top: 0; bottom: 0; }
.timeline-axis { display: flex; justify-content: space-between; color: var(--muted); font-size: 0.75rem; margin-top: 4px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 12px; margin-top: 10px; font-size: 0.8rem; color: var(--muted); }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: middle; }
.state-alive { background: var(--ok); }
.state-dead { background: var(--bad); }
.state-disconnected { background: #b04ad8; }
.state-frozen { background: #4fb3d9; }
.state-blind { background: var(--warn); }
.state-closed, .state-none { background: #3a3f4b; }

.live-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
.live-header h1 { margin: 4px 0; }
.quality { display: flex; gap: 6px; }
.live-stage { position: relative; background: #000; border-radius: 10px; overflow: hidden; aspect-ratio: 16 / 9; margin-top: 10px; }
.live-frame { display: block; width: 100%; height: 100%; object-fit: contain; }
.live-overlay {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  text-align: center; padding: 16px; background: rgba(0, 0, 0, 0.55); font-weight: 600;
}
.live-stage:fullscreen { border-radius: 0; aspect-ratio: auto; width: 100vw; height: 100vh; }

/* Phone turned sideways on the live screen: the picture takes the whole screen. */
@media (orientation: landscape) and (max-height: 500px) {
  body.live-mode nav.tabs, body.live-mode .live-header { display: none; }
  body.live-mode #screen { padding: 0; max-width: none; }
  body.live-mode .live-stage { margin: 0; border-radius: 0; width: 100vw; height: 100vh; aspect-ratio: auto; }
}
```

- [ ] **Step 5: JS ortak modüller ve yönlendirici**

`web/js/api.js`:
```js
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  if (!response.ok) {
    throw new ApiError(response.status, `${path}: HTTP ${response.status}`);
  }
  return response.json();
}

export const getStatus = () => request("/api/status");
export const getEvents = (limit = 50) => request(`/api/events?limit=${limit}`);
export const getSnapshots = (since) => request(`/api/snapshots?since=${since}`);
export const getVapidKey = () => request("/api/push/vapid-key");
export const sendTestPush = () => request("/api/push/test", { method: "POST" });

export function subscribePush(subscriptionJson) {
  return request("/api/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscriptionJson),
  });
}

/** quality null → the server's configured default ([api] stream_quality). */
export function streamUrl(quality) {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const query = quality ? `?quality=${encodeURIComponent(quality)}` : "";
  return `${scheme}://${location.host}/api/stream${query}`;
}
```

`web/js/ui.js`:
```js
export const STATE_LABELS = {
  alive: { text: "Canlı", tone: "ok" },
  dead: { text: "Ölü", tone: "bad" },
  disconnected: { text: "Bağlantı koptu", tone: "bad" },
  frozen: { text: "Donmuş", tone: "warn" },
  blind: { text: "Kör (izlenemiyor)", tone: "warn" },
  closed: { text: "Oyun kapalı", tone: "off" },
};

// Same titles as src/ko_monitor/messages.py TITLES.
export const EVENT_LABELS = {
  game_started: "▶️ Oyun açıldı",
  game_closed: "❌ Oyun kapandı",
  dead: "💀 Karakter öldü",
  disconnected: "🔌 Sunucudan düştün",
  frozen: "🧊 Oyun ekranı dondu",
  blind: "🙈 İzleme yapılamıyor",
  recovered: "✅ Düzeldi",
  inventory_full: "🎒 Envanter dolu",
  test: "🔔 Test bildirimi",
};

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  node.append(...children.filter((child) => child !== null && child !== undefined));
  return node;
}

export function stateLabel(state) {
  return STATE_LABELS[state] || { text: "Bilinmiyor", tone: "off" };
}

export function eventLabel(kind) {
  return EVENT_LABELS[kind] || kind;
}

export function agoText(seconds) {
  if (seconds === null || seconds === undefined) return "hiç";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} sn önce`;
  if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
  if (s < 86400) return `${Math.floor(s / 3600)} sa önce`;
  return `${Math.floor(s / 86400)} gün önce`;
}

export function clockText(ts) {
  return new Date(ts * 1000).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

export function dateTimeText(ts) {
  return new Date(ts * 1000).toLocaleString("tr-TR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export function numberText(value) {
  return value === null || value === undefined ? "—" : Number(value).toLocaleString("tr-TR");
}

export function eventItem(event) {
  const meta = [event.detail, dateTimeText(event.ts)].filter(Boolean).join(" · ");
  return el("li", {}, el("span", { class: "event-kind" }, eventLabel(event.kind)), el("span", { class: "meta" }, meta));
}
```

`web/js/app.js`:
```js
import settings from "./screens/settings.js";

// Route name → screen module. The first entry is the default route.
const SCREENS = { settings };

const root = document.getElementById("screen");
let unmount = null;

function currentRoute() {
  const name = location.hash.replace(/^#\/?/, "").split("?")[0];
  return SCREENS[name] ? name : Object.keys(SCREENS)[0];
}

function render() {
  const route = currentRoute();
  if (unmount) {
    unmount();
    unmount = null;
  }
  root.replaceChildren();
  document.title = `${SCREENS[route].title} · KO Monitor`;
  for (const link of document.querySelectorAll("nav.tabs a")) {
    link.classList.toggle("active", link.dataset.route === route);
  }
  unmount = SCREENS[route].mount(root) || null;
}

window.addEventListener("hashchange", render);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch((error) => console.error("service worker:", error));
  // A tapped notification asks an already open window to show its page (see sw.js).
  navigator.serviceWorker.addEventListener("message", (event) => {
    if (event.data && event.data.type === "navigate") {
      location.hash = new URL(event.data.url, location.origin).hash || "#/events";
    }
  });
}

render();
```

- [ ] **Step 6: Ayarlar ekranı**

`web/js/screens/settings.js`:
```js
import { getVapidKey, sendTestPush, subscribePush } from "../api.js";
import { el } from "../ui.js";

function base64UrlToBytes(value) {
  const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function sameKey(subscription, keyBytes) {
  const current = subscription.options && subscription.options.applicationServerKey;
  if (!current) return false;
  const bytes = new Uint8Array(current);
  return bytes.length === keyBytes.length && bytes.every((value, index) => value === keyBytes[index]);
}

function isStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
}

function pushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

async function enableNotifications() {
  // iOS only shows the permission prompt when it is requested directly from the tap.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Bildirim izni verilmedi.");
  }
  const registration = await navigator.serviceWorker.ready;
  const { key } = await getVapidKey();
  const keyBytes = base64UrlToBytes(key);
  let subscription = await registration.pushManager.getSubscription();
  if (subscription && !sameKey(subscription, keyBytes)) {
    await subscription.unsubscribe(); // the PC's VAPID key changed; the old subscription cannot be used
    subscription = null;
  }
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes });
  }
  await subscribePush(subscription.toJSON());
}

export default {
  title: "Ayarlar",
  mount(root) {
    const statusLine = el("p", { class: "note" });
    const show = (text, tone = "") => {
      statusLine.textContent = text;
      statusLine.className = `note ${tone}`;
    };
    const enableButton = el("button", { class: "primary", type: "button" }, "Bildirimleri aç");
    const testButton = el("button", { type: "button" }, "Test bildirimi gönder");
    const hints = [];

    if (!isStandalone()) {
      hints.push(el("p", { class: "note warn" },
        "iPhone'da bildirim için önce Safari → Paylaş → Ana Ekrana Ekle ile uygulamayı kur ve ana ekrandaki simgeden aç."));
    }
    if (!pushSupported()) {
      enableButton.disabled = true;
      hints.push(el("p", { class: "note bad" }, "Bu tarayıcı Web Push desteklemiyor (iPhone'da iOS 16.4 veya üstü gerekir)."));
    } else if (Notification.permission === "granted") {
      show("Bildirim izni verilmiş. Aboneliği yenilemek için yine de 'Bildirimleri aç'a dokunabilirsin.", "ok");
    } else if (Notification.permission === "denied") {
      show("Bildirim izni reddedilmiş. iPhone Ayarlar → Bildirimler → KO Monitor'dan izin ver.", "bad");
    }

    enableButton.addEventListener("click", async () => {
      enableButton.disabled = true;
      show("Bildirimler açılıyor…");
      try {
        await enableNotifications();
        show("Bildirimler açık. Şimdi test bildirimi gönderebilirsin.", "ok");
      } catch (error) {
        show(`Açılamadı: ${error.message}`, "bad");
      } finally {
        enableButton.disabled = false;
      }
    });

    testButton.addEventListener("click", async () => {
      testButton.disabled = true;
      show("Gönderiliyor…");
      try {
        const result = await sendTestPush();
        if (result.delivered) show("Test bildirimi gönderildi.", "ok");
        else if (result.subscriptions === 0) show("Kayıtlı abonelik yok. Önce 'Bildirimleri aç'a dokun.", "warn");
        else show("Gönderilemedi. Bilgisayardaki logs\\agent.log dosyasına bak.", "bad");
      } catch (error) {
        show(`Hata: ${error.message}`, "bad");
      } finally {
        testButton.disabled = false;
      }
    });

    root.append(
      el("h1", {}, "Ayarlar"),
      el("section", { class: "card" },
        el("h2", {}, "Bildirimler"),
        ...hints,
        el("div", { class: "buttons" }, enableButton, testButton),
        statusLine),
    );
    return null;
  },
};
```

- [ ] **Step 7: Service worker**

`web/sw.js`:
```js
const CACHE = "ko-monitor-v1";
// Every file under web/js must be listed (tests/test_web.py checks it). Bump CACHE when this list changes.
const SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/manifest.webmanifest",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/js/app.js",
  "/js/api.js",
  "/js/ui.js",
  "/js/screens/settings.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

// Network first (the PC is the only source of truth), cached shell when offline. API calls are never cached.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("/index.html"))),
  );
});

// Payload is exactly messages.render(): {title, body, url, kind, ts}.
self.addEventListener("push", (event) => {
  let message = { title: "KO Monitor", body: "", url: "/#/events", kind: "unknown", ts: Date.now() / 1000 };
  if (event.data) {
    try {
      message = { ...message, ...event.data.json() };
    } catch (error) {
      message.body = event.data.text();
    }
  }
  event.waitUntil(
    self.registration.showNotification(message.title, {
      body: message.body,
      tag: `${message.kind}-${message.ts}`,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: message.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/#/events", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) {
          client.postMessage({ type: "navigate", url: target });
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
```

- [ ] **Step 8: Spec'e sapmayı işle**

`docs/superpowers/specs/2026-09-15-ko-monitor-design.md` içinde üç satırı değiştir.

§2 tablosunda:
```markdown
| **Telefon: iPhone + PWA (React).** | Expo ile bildirim için yıllık Apple geliştirici hesabı gerekir; PWA ücretsiz. |
```
yerine:
```markdown
| **Telefon: iPhone + PWA (derleme adımı olmayan HTML/CSS/JavaScript).** | Expo ile bildirim için yıllık Apple geliştirici hesabı gerekir; PWA ücretsiz. Bilgisayarda Node.js kurulu değil; yeni yazılım kurmamak için React + Vite yerine derleme gerektirmeyen vanilla ES modülleri seçildi (Plan 2). |
```

§3 bileşen tablosunda:
```markdown
| `api` | FastAPI; yalnızca `127.0.0.1` üzerinde dinler; PWA'nın build dosyalarını da sunar. | FastAPI, uvicorn |
| `pwa` | React + Vite + TypeScript + `vite-plugin-pwa`. | — |
```
yerine:
```markdown
| `api` | FastAPI; yalnızca `127.0.0.1` üzerinde dinler; PWA'nın statik dosyalarını (`web/`) da sunar. Ajan döngüsüyle aynı süreçte, ayrı iş parçacığında çalışır. | FastAPI, uvicorn, websockets |
| `pwa` | Vanilla HTML/CSS/JavaScript ES modülleri, derleme adımı yok; manifest ve service worker elle yazılır, ikonlar `scripts/make_icons.py` ile üretilir. (İlk taslakta React + Vite + TypeScript + `vite-plugin-pwa` idi; bu PC'de Node.js olmadığı için değiştirildi.) | — |
```

- [ ] **Step 9: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_web.py tests/test_api.py -q`
Expected: PASS (hepsi)

- [ ] **Step 10: Elle doğrulama (PC tarayıcısı)**

1. Ayrı pencerede `.venv\Scripts\python.exe -m ko_monitor run`; Edge veya Chrome'da `http://127.0.0.1:8765/` aç.
2. Ayarlar ekranı görünür; alt sekme çubuğunda dört sekme var (Durum/Canlı/Olaylar da şimdilik Ayarlar'ı gösterir — Task 6-7'de dolacak). Tarayıcı konsolunda hata yok.
3. DevTools → Application → Manifest: ad "KO Monitor", display `standalone`, üç ikon görünür, hata/uyarı yok.
4. DevTools → Application → Service Workers: `sw.js` "activated and is running"; Cache Storage → `ko-monitor-v1` içinde SHELL'deki 11 girdi var.
5. "Bildirimleri aç" → izin istemi → İzin ver → yeşil "Bildirimler açık" yazısı. Doğrula: `.venv\Scripts\python.exe -c "from pathlib import Path; from ko_monitor.storage import Storage; s = Storage(Path('data/ko_monitor.sqlite3')); print(len(s.subscriptions())); s.close()"` → `1` veya daha fazla.
6. "Test bildirimi gönder" → masaüstünde "🔔 Test bildirimi" bildirimi; tıklayınca sekme öne gelir ve adres `#/events` olur.
7. DevTools → Application → Service Workers → "Push" alanına `{"title":"💀 Karakter öldü","body":"Ronark Land · 11:42","url":"/#/events","kind":"dead","ts":1}` yazıp Push → aynı başlık ve gövdeyle bildirim görünür.
8. Süreci Ctrl+C ile kapat. (Masaüstü tarayıcı aboneliği veritabanında kalabilir; PC'ye de bildirim gelmesini istemiyorsan tarayıcıda site bildirim iznini kaldır — ilk gönderimde 404/410 dönen abonelik otomatik silinir.)

- [ ] **Step 11: Commit**

```powershell
git add scripts/make_icons.py web/index.html web/styles.css web/manifest.webmanifest web/sw.js web/icons/icon-180.png web/icons/icon-192.png web/icons/icon-512.png web/js/app.js web/js/api.js web/js/ui.js web/js/screens/settings.js docs/superpowers/specs/2026-09-15-ko-monitor-design.md tests/test_web.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: pwa shell with manifest, icons, service worker push and settings screen" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Durum ve Olaylar ekranları

**Files:**
- Create: `web/js/screens/status.js`, `web/js/screens/events.js`
- Modify: `web/js/app.js` (import satırları + `SCREENS`), `web/sw.js` (`CACHE` + `SHELL`)
- Test: `tests/test_web.py` (bir test eklenir)

**Interfaces:**
- Consumes: ekran sözleşmesi `{title, mount(root) -> cleanup}`, `getStatus()`, `getEvents(limit)`, `getSnapshots(since)` (`api.js`), `el`, `stateLabel`, `agoText`, `clockText`, `numberText`, `eventItem` (`ui.js`), CSS sınıfları (Task 5); `/api/status` alanları `server_time, updated_at, state, readings.hp, readings.hp_max, zone_last, money_last, slots_used_last, slots_total_last, inventory_seen_at` (Task 1-2); `/api/snapshots` öğeleri `{ts, state, ...}` eskiden yeniye (Task 2).
- Produces: `status.js` default export (5 sn'de bir sorgu, sayfa gizliyken durur); `events.js` default export + `export function buildSegments(snapshots, start, end, maxGapS = 90) -> Array<{from, to, state}>`; `SCREENS = { status, events, settings }` (varsayılan rota `status`).

- [ ] **Step 1: Failing test yaz**

`tests/test_web.py` sonuna ekle:
```python
def test_status_and_events_screens_are_registered_first_status():
    screens = registered_screens()
    assert screens[0] == "status"
    assert {"status", "events", "settings"} <= set(screens)
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_web.py -q`
Expected: FAIL — `test_status_and_events_screens_are_registered_first_status` (`assert 'settings' == 'status'`)

- [ ] **Step 3: Durum ekranı**

`web/js/screens/status.js`:
```js
import { getEvents, getStatus } from "../api.js";
import { agoText, clockText, el, eventItem, numberText, stateLabel } from "../ui.js";

const POLL_MS = 5000;
const STALE_S = 30; // the agent publishes every 2 s (10 s while the game is closed)

function hpBlock(readings) {
  const hp = readings ? readings.hp : null;
  const max = readings ? readings.hp_max : null;
  if (hp === null || hp === undefined || !max) {
    return el("p", { class: "meta" }, "HP: okunamadı");
  }
  const percent = Math.max(0, Math.min(100, (hp / max) * 100));
  return el("div", {},
    el("div", { class: "row" }, el("span", {}, "HP"), el("span", {}, `${numberText(hp)} / ${numberText(max)}`)),
    el("div", { class: "hpbar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": max, "aria-valuenow": hp },
      el("span", { style: `width: ${percent.toFixed(1)}%` })));
}

function stateCard(status) {
  const label = stateLabel(status.state);
  let updated = "Ajan henüz veri göndermedi";
  let stale = true;
  if (status.updated_at !== null && status.updated_at !== undefined) {
    const age = status.server_time - status.updated_at;
    stale = age > STALE_S;
    updated = `Son güncelleme ${agoText(age)}`;
  }
  return el("section", { class: "card" },
    el("div", { class: "row" },
      el("span", { class: `badge ${label.tone}` }, label.text),
      el("span", { class: stale ? "meta warn" : "meta" }, updated)),
    el("p", { class: "meta" }, status.zone_last ? `Bölge: ${status.zone_last}` : "Bölge: bilinmiyor"),
    hpBlock(status.readings));
}

function inventoryCard(status) {
  const seen = status.inventory_seen_at;
  const slots = status.slots_used_last === null || status.slots_used_last === undefined
    ? "—"
    : `${status.slots_used_last} / ${status.slots_total_last}`;
  const seenText = seen === null || seen === undefined
    ? "hiç (envanter penceresi açılınca okunur)"
    : `${clockText(seen)} (${agoText(status.server_time - seen)})`;
  return el("section", { class: "card" },
    el("h2", {}, "Envanter (son görülen)"),
    el("dl", { class: "kv" },
      el("dt", {}, "Para"), el("dd", {}, numberText(status.money_last)),
      el("dt", {}, "Slotlar"), el("dd", {}, slots),
      el("dt", {}, "Görüldü"), el("dd", {}, seenText)));
}

function eventsCard(events) {
  return el("section", { class: "card" },
    el("h2", {}, "Son olaylar"),
    events.length
      ? el("ul", { class: "event-list" }, ...events.map(eventItem))
      : el("p", { class: "meta" }, "Henüz olay yok."));
}

export default {
  title: "Durum",
  mount(root) {
    const errorLine = el("p", { class: "note bad", hidden: true });
    const body = el("div", {}, el("p", { class: "meta" }, "Yükleniyor…"));
    root.append(el("h1", {}, "Durum"), errorLine, body);

    let active = true;
    let timer = null;

    async function refresh() {
      try {
        const [status, events] = await Promise.all([getStatus(), getEvents(5)]);
        if (!active) return;
        errorLine.hidden = true;
        body.replaceChildren(stateCard(status), inventoryCard(status), eventsCard(events));
      } catch (error) {
        if (!active) return;
        // Keep the last good data on screen; only say that it is not fresh.
        errorLine.textContent = `Bilgisayara ulaşılamıyor (Tailscale açık mı?): ${error.message}`;
        errorLine.hidden = false;
      }
    }

    function start() {
      if (timer !== null) return;
      refresh();
      timer = setInterval(refresh, POLL_MS);
    }

    function stop() {
      clearInterval(timer);
      timer = null;
    }

    function onVisibility() {
      if (document.hidden) stop();
      else start();
    }

    document.addEventListener("visibilitychange", onVisibility);
    if (!document.hidden) start();
    return () => {
      active = false;
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  },
};
```

- [ ] **Step 4: Olaylar ekranı (liste + 24 saatlik zaman çizelgesi)**

`web/js/screens/events.js`:
```js
import { getEvents, getSnapshots } from "../api.js";
import { clockText, el, eventItem, stateLabel } from "../ui.js";

const DAY_S = 86400;
const MAX_GAP_S = 90; // snapshots arrive every 60 s while the game is open; a longer gap means "no data"
const LEGEND_STATES = ["alive", "dead", "disconnected", "frozen", "blind"];

/** Snapshots (oldest first) → merged [from, to) pieces of one state, clipped to [start, end]. */
export function buildSegments(snapshots, start, end, maxGapS = MAX_GAP_S) {
  const segments = [];
  snapshots.forEach((snapshot, index) => {
    const next = snapshots[index + 1];
    const covered = next ? Math.min(next.ts, snapshot.ts + maxGapS) : snapshot.ts + maxGapS;
    const from = Math.max(snapshot.ts, start);
    const to = Math.min(covered, end);
    if (to <= from) return;
    const last = segments[segments.length - 1];
    if (last && last.state === snapshot.state && Math.abs(last.to - from) < 1) {
      last.to = to;
    } else {
      segments.push({ from, to, state: snapshot.state });
    }
  });
  return segments;
}

function timelineCard(snapshots, start, end) {
  const span = end - start;
  const bar = el("div", { class: "timeline", role: "img", "aria-label": "Son 24 saatin durum çizelgesi" });
  for (const segment of buildSegments(snapshots, start, end)) {
    const label = stateLabel(segment.state);
    const left = ((segment.from - start) / span) * 100;
    const width = Math.max(0.2, ((segment.to - segment.from) / span) * 100);
    bar.append(el("span", {
      class: `seg state-${segment.state}`,
      title: `${label.text}: ${clockText(segment.from)}–${clockText(segment.to)}`,
      style: `left: ${left.toFixed(3)}%; width: ${width.toFixed(3)}%`,
    }));
  }
  const axis = el("div", { class: "timeline-axis" });
  for (let i = 0; i <= 4; i += 1) {
    axis.append(el("span", {}, clockText(start + (span * i) / 4)));
  }
  const legend = el("div", { class: "legend" },
    ...LEGEND_STATES.map((state) => el("span", {}, el("i", { class: `dot state-${state}` }), stateLabel(state).text)),
    el("span", {}, el("i", { class: "dot state-none" }), "Veri yok / oyun kapalı"));
  return el("section", { class: "card" }, el("h2", {}, "Son 24 saat"), bar, axis, legend);
}

function listCard(events) {
  return el("section", { class: "card" },
    el("h2", {}, "Tüm olaylar"),
    events.length
      ? el("ul", { class: "event-list" }, ...events.map(eventItem))
      : el("p", { class: "meta" }, "Henüz olay yok."));
}

export default {
  title: "Olaylar",
  mount(root) {
    const refreshButton = el("button", { type: "button" }, "Yenile");
    const errorLine = el("p", { class: "note bad", hidden: true });
    const body = el("div", {}, el("p", { class: "meta" }, "Yükleniyor…"));
    root.append(el("div", { class: "row" }, el("h1", {}, "Olaylar"), refreshButton), errorLine, body);

    let active = true;
    let loading = false;

    async function refresh() {
      if (loading) return;
      loading = true;
      refreshButton.disabled = true;
      const end = Date.now() / 1000;
      const start = end - DAY_S;
      try {
        const [events, snapshots] = await Promise.all([getEvents(100), getSnapshots(start)]);
        if (!active) return;
        errorLine.hidden = true;
        body.replaceChildren(timelineCard(snapshots, start, end), listCard(events));
      } catch (error) {
        if (!active) return;
        errorLine.textContent = `Bilgisayara ulaşılamıyor (Tailscale açık mı?): ${error.message}`;
        errorLine.hidden = false;
      } finally {
        loading = false;
        refreshButton.disabled = false;
      }
    }

    function onVisibility() {
      if (!document.hidden) refresh();
    }

    refreshButton.addEventListener("click", refresh);
    document.addEventListener("visibilitychange", onVisibility);
    refresh();
    return () => {
      active = false;
      document.removeEventListener("visibilitychange", onVisibility);
    };
  },
};
```

- [ ] **Step 5: Ekranları kaydet ve önbellek listesini güncelle**

`web/js/app.js` içinde:
```js
import settings from "./screens/settings.js";

// Route name → screen module. The first entry is the default route.
const SCREENS = { settings };
```
yerine:
```js
import events from "./screens/events.js";
import settings from "./screens/settings.js";
import status from "./screens/status.js";

// Route name → screen module. The first entry is the default route.
const SCREENS = { status, events, settings };
```

`web/sw.js` içinde `const CACHE = ...` satırından `];` satırına kadarki blok:
```js
const CACHE = "ko-monitor-v2";
// Every file under web/js must be listed (tests/test_web.py checks it). Bump CACHE when this list changes.
const SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/manifest.webmanifest",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/js/app.js",
  "/js/api.js",
  "/js/ui.js",
  "/js/screens/events.js",
  "/js/screens/settings.js",
  "/js/screens/status.js",
];
```

- [ ] **Step 6: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_web.py -q`
Expected: PASS (hepsi; `test_relative_imports_resolve` artık `events.js` ve `status.js` için de çalışır)

- [ ] **Step 7: Elle doğrulama (PC tarayıcısı)**

1. `.venv\Scripts\python.exe -m ko_monitor run` çalışırken `http://127.0.0.1:8765/` aç → varsayılan olarak Durum ekranı; rozet "Oyun kapalı" (oyun kapalıysa) veya "Canlı"; "Son güncelleme N sn önce" her 5 sn'de yenilenir (DevTools → Network'te `/api/status` ve `/api/events?limit=5` 5 sn arayla).
2. Başka sekmeye geç, 20 sn bekle, geri dön → gizliyken `/api/status` isteği yok, dönünce hemen bir istek.
3. Sunucuyu Ctrl+C ile durdur → Durum ekranında kırmızı "Bilgisayara ulaşılamıyor" satırı çıkar, son veriler ekranda kalır; sunucuyu yeniden başlatınca satır kaybolur.
4. Oyun açıkken en az birkaç dakika çalıştıktan sonra Olaylar ekranı: çizelgede yeşil bir parça ve saat ekseni (5 etiket), altında olay listesi ("▶️ Oyun açıldı" vb.). Oyun hiç açılmadıysa çizelge boş gri, liste "Henüz olay yok." veya geçmiş olaylar.
5. Konsolda hata yok; DevTools → Cache Storage'da `ko-monitor-v2` var, `ko-monitor-v1` silinmiş.

- [ ] **Step 8: Commit**

```powershell
git add web/js/screens/status.js web/js/screens/events.js web/js/app.js web/sw.js tests/test_web.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: status and events screens with 24 hour state timeline" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Canlı ekranı — WebSocket görüntü, kalite seçimi, yeniden bağlanma

**Files:**
- Create: `web/js/screens/live.js`
- Modify: `web/js/app.js` (import + `SCREENS`), `web/sw.js` (`CACHE` + `SHELL`)
- Test: `tests/test_web.py` (bir test eklenir)

**Interfaces:**
- Consumes: `streamUrl(quality: string | null)` (`api.js`), `el` (`ui.js`), CSS sınıfları `live-mode live-header quality live-stage live-frame live-overlay active` (Task 5); `WS /api/stream` mesajları: ikili = JPEG kare, metin = `{"status": "minimized" | "not_found" | "black" | "ok"}` (Task 3); ekran sözleşmesi (Task 5).
- Produces: `live.js` default export; `SCREENS = { status, live, events, settings }` — sekme çubuğundaki dört rotanın tamamı kayıtlı.

- [ ] **Step 1: Failing test yaz**

`tests/test_web.py` sonuna ekle:
```python
def test_every_tab_has_a_screen_in_tab_order():
    assert registered_screens() == tab_routes() == ["status", "live", "events", "settings"]
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_web.py -q`
Expected: FAIL — `test_every_tab_has_a_screen_in_tab_order` (`['status', 'events', 'settings'] == [...]`)

- [ ] **Step 3: Canlı ekranı**

`web/js/screens/live.js`:
```js
import { streamUrl } from "../api.js";
import { el } from "../ui.js";

const QUALITIES = [["low", "Düşük"], ["medium", "Orta"], ["high", "Yüksek"]];
const STORAGE_KEY = "ko-monitor.quality";
const RECONNECT_MS = [1000, 2000, 5000, 10000];
const STATUS_TEXT = {
  minimized: "Oyun penceresi küçültülmüş, görüntü alınamıyor",
  not_found: "Oyun penceresi bulunamadı",
  black: "Ekran siyah",
};

function loadQuality() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return QUALITIES.some(([key]) => key === saved) ? saved : null;
  } catch (error) {
    return null; // storage unavailable: use the server default
  }
}

function saveQuality(quality) {
  try {
    localStorage.setItem(STORAGE_KEY, quality);
  } catch (error) {
    // storage unavailable: the choice lasts until the screen is left
  }
}

export default {
  title: "Canlı",
  mount(root) {
    let quality = loadQuality(); // null → the server's [api] stream_quality
    let socket = null;
    let retryTimer = null;
    let attempts = 0;
    let frameUrl = null;
    let active = true;

    const image = el("img", { class: "live-frame", alt: "Canlı oyun görüntüsü" });
    const overlay = el("div", { class: "live-overlay" }, "Bağlanıyor…");
    const stage = el("div", { class: "live-stage" }, image, overlay);
    const buttons = QUALITIES.map(([key, text]) => el("button", { type: "button", "data-quality": key }, text));
    const fullscreenButton = el("button", { type: "button" }, "Tam ekran");
    const hint = el("p", { class: "meta" });

    function showOverlay(text) {
      overlay.textContent = text;
      overlay.hidden = !text;
    }

    function markQuality() {
      for (const button of buttons) {
        button.classList.toggle("active", button.dataset.quality === quality);
      }
      hint.textContent = (quality ? "" : "Kalite seçilmedi: bilgisayardaki varsayılan kullanılıyor. ")
        + "Telefonu yan çevirince görüntü tam ekran olur.";
    }

    function showFrame(blob) {
      const previous = frameUrl;
      frameUrl = URL.createObjectURL(blob);
      image.src = frameUrl;
      if (previous) URL.revokeObjectURL(previous);
    }

    function connect() {
      clearTimeout(retryTimer);
      retryTimer = null;
      if (!active || socket) return;
      if (document.hidden) {
        showOverlay("Duraklatıldı");
        return;
      }
      showOverlay(attempts ? "Yeniden bağlanıyor…" : "Bağlanıyor…");
      const ws = new WebSocket(streamUrl(quality));
      ws.binaryType = "blob";
      socket = ws;
      ws.onmessage = (event) => {
        if (socket !== ws) return;
        if (typeof event.data === "string") {
          let status = "";
          try {
            status = JSON.parse(event.data).status;
          } catch (error) {
            status = "";
          }
          showOverlay(STATUS_TEXT[status] || "Görüntü bekleniyor…");
          return;
        }
        attempts = 0;
        showOverlay("");
        showFrame(event.data);
      };
      ws.onclose = () => {
        if (socket !== ws) return; // closed on purpose: quality change, page hidden or screen left
        socket = null;
        if (!active || document.hidden) return;
        const delay = RECONNECT_MS[Math.min(attempts, RECONNECT_MS.length - 1)];
        attempts += 1;
        showOverlay(`Bağlantı koptu, ${Math.round(delay / 1000)} sn içinde yeniden denenecek…`);
        retryTimer = setTimeout(connect, delay);
      };
    }

    function disconnect() {
      clearTimeout(retryTimer);
      retryTimer = null;
      const ws = socket;
      socket = null;
      if (ws) ws.close(); // the server stops capturing and encoding for this viewer
    }

    function onVisibility() {
      if (document.hidden) {
        disconnect();
        showOverlay("Duraklatıldı");
      } else {
        attempts = 0;
        connect();
      }
    }

    for (const button of buttons) {
      button.addEventListener("click", () => {
        if (button.dataset.quality === quality) return;
        quality = button.dataset.quality;
        saveQuality(quality);
        markQuality();
        disconnect();
        attempts = 0;
        connect();
      });
    }

    fullscreenButton.hidden = !(stage.requestFullscreen || stage.webkitRequestFullscreen);
    fullscreenButton.addEventListener("click", () => {
      if (stage.requestFullscreen) stage.requestFullscreen().catch(() => {});
      else stage.webkitRequestFullscreen();
    });

    root.append(
      el("div", { class: "live-header" },
        el("h1", {}, "Canlı"),
        el("div", { class: "quality" }, ...buttons, fullscreenButton)),
      stage,
      hint,
    );
    document.body.classList.add("live-mode");
    document.addEventListener("visibilitychange", onVisibility);
    markQuality();
    connect();

    return () => {
      active = false;
      disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      document.body.classList.remove("live-mode");
      if (frameUrl) URL.revokeObjectURL(frameUrl);
    };
  },
};
```

- [ ] **Step 4: Ekranı kaydet ve önbellek listesini güncelle**

`web/js/app.js` içinde:
```js
import events from "./screens/events.js";
import settings from "./screens/settings.js";
import status from "./screens/status.js";

// Route name → screen module. The first entry is the default route.
const SCREENS = { status, events, settings };
```
yerine:
```js
import events from "./screens/events.js";
import live from "./screens/live.js";
import settings from "./screens/settings.js";
import status from "./screens/status.js";

// Route name → screen module. The first entry is the default route.
const SCREENS = { status, live, events, settings };
```

`web/sw.js` içinde `const CACHE = ...` satırından `];` satırına kadarki blok:
```js
const CACHE = "ko-monitor-v3";
// Every file under web/js must be listed (tests/test_web.py checks it). Bump CACHE when this list changes.
const SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/manifest.webmanifest",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/js/app.js",
  "/js/api.js",
  "/js/ui.js",
  "/js/screens/events.js",
  "/js/screens/live.js",
  "/js/screens/settings.js",
  "/js/screens/status.js",
];
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_web.py tests/test_stream.py -q`
Expected: PASS (hepsi)

- [ ] **Step 6: Elle doğrulama (PC tarayıcısı)**

1. `.venv\Scripts\python.exe -m ko_monitor run` çalışırken `http://127.0.0.1:8765/#/live` aç.
2. Oyun kapalıyken: kaplamada "Oyun penceresi bulunamadı"; DevTools → Network → WS → `/api/stream` bağlantısında ~10 metin mesajı/sn.
3. Görüntü denemesi (oyun açıksa oyunla; değilse isteğe bağlı: ayrı bir PowerShell penceresinde `$host.UI.RawUI.WindowTitle = "Knight Evolution"` — pencere başlığı bu olunca yakalama o pencereyi gösterir; Windows Terminal'de başlık sekme başlığından gelir): görüntü akar, kaplama kaybolur.
4. "Düşük" → WS yeniden açılır, adres `?quality=low`, kareler küçülür (Network'te mesaj boyutu düşer, ~5/sn); "Yüksek" → ~20/sn. Sayfayı yenile → seçim hatırlanır. Sunucu logunda `capture update interval ... ms` satırı görünür (oyun/pencere varken).
5. Başka sekmeye geç → WS kapanır, sunucu logunda `live viewer disconnected`; geri dön → yeniden bağlanır.
6. Durum sekmesine geç → WS kapanır ve bir daha açılmaz; logda `capture update interval 100 ms -> 1000 ms` (pencere varken) — ajan boşta hızına döner.
7. Canlı ekranda sunucuyu Ctrl+C ile durdur → "Bağlantı koptu, 1 sn içinde…", ardından 2, 5, 10 sn; sunucuyu yeniden başlat → sayfa yenilemeden görüntü/durum geri gelir.
8. DevTools cihaz araç çubuğunda yatay telefon boyutu (ör. 844x390) → sekme çubuğu ve başlık gizlenir, görüntü tüm ekranı kaplar.

- [ ] **Step 7: Commit**

```powershell
git add web/js/screens/live.js web/js/app.js web/sw.js tests/test_web.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: live screen with websocket frames, quality presets and auto reconnect" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Kurulum belgesi ve otomatik başlatma script'i

Bu görev sistem yapılandırmasını **değiştirmez**: script yazılır ve yalnızca sözdizimi denetlenir (çalıştırılmaz); Tailscale, healthchecks.io, ntfy ve iPhone adımları kullanıcı için belgelenir. Uygulayıcı hiçbir hesap açmaz, oturum açmaz, `tailscale` komutu ya da `Register-ScheduledTask` çalıştırmaz.

**Files:**
- Create: `scripts/install-autostart.ps1`
- Create: `docs/setup.md`
- Test: `tests/test_scripts.py`

**Interfaces:**
- Consumes: CLI `python -m ko_monitor run` (Task 4); `config.example.toml` `[api]`, `[push]`, `[heartbeat]` (Task 1 + mevcut); Ayarlar ekranı düğmeleri "Bildirimleri aç" / "Test bildirimi gönder" (Task 5); `logs\agent.log` (mevcut).
- Produces: Görev Zamanlayıcı görevi `KO Monitor` (kullanıcı kaydeder): oturum açılışında, çalışma klasörü proje kökü, `.venv\Scripts\pythonw.exe -m ko_monitor run`, hata olursa 1 dk arayla yeniden başlatma; `docs/setup.md` (Türkçe).

- [ ] **Step 1: Failing testleri yaz**

`tests/test_scripts.py`:
```python
import shutil
import subprocess

import pytest

from helpers import ROOT

SCRIPT = ROOT / "scripts" / "install-autostart.ps1"
SETUP = ROOT / "docs" / "setup.md"


def test_autostart_script_is_ascii():
    # Windows PowerShell 5.1 reads BOM-less files with the ANSI code page; ASCII avoids mangled text.
    assert SCRIPT.read_bytes().isascii()


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell not available")
def test_autostart_script_parses_without_running_it():
    command = (
        "$errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT}', [ref]$null, [ref]$errors) | Out-Null; "
        "$errors.Count"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0"


def test_autostart_script_registers_a_logon_task_that_restarts_in_the_project_root():
    text = SCRIPT.read_text(encoding="utf-8")
    for needle in (
        "New-ScheduledTaskTrigger -AtLogOn",
        "-RestartCount",
        "-RestartInterval",
        "-WorkingDirectory $projectRoot",
        '"-m ko_monitor run"',
        "pythonw.exe",
        "Register-ScheduledTask",
    ):
        assert needle in text, needle


def test_setup_guide_covers_every_step():
    text = SETUP.read_text(encoding="utf-8")
    for needle in (
        "config.example.toml",
        "healthchecks.io",
        "ntfy",
        "tailscale serve --bg 8765",
        "Ana Ekrana Ekle",
        "Bildirimleri aç",
        "Test bildirimi gönder",
        "iOS 16.4",
        "install-autostart.ps1",
        "Unregister-ScheduledTask",
    ):
        assert needle in text, needle
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_scripts.py -q`
Expected: FAIL — `FileNotFoundError` (`scripts\install-autostart.ps1`, `docs\setup.md`)

- [ ] **Step 3: Otomatik başlatma script'ini yaz (ÇALIŞTIRMA)**

`scripts/install-autostart.ps1` (yalnızca ASCII karakter):
```powershell
<#
.SYNOPSIS
  Registers the "KO Monitor" Task Scheduler task: starts the agent and phone API at logon,
  restarts it every minute if it fails.

.NOTES
  The user runs this once, from the project root, in a normal (non-admin) PowerShell:
      powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
  Start now:  Start-ScheduledTask -TaskName "KO Monitor"
  Remove:     Unregister-ScheduledTask -TaskName "KO Monitor" -Confirm:$false
#>
[CmdletBinding()]
param(
    [string]$TaskName = "KO Monitor"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"  # pythonw: no console window
if (-not (Test-Path $python)) {
    throw "Sanal ortam bulunamadi: $python (once docs\setup.md adim 1)"
}
if (-not (Test-Path (Join-Path $projectRoot "config.toml"))) {
    Write-Warning "config.toml yok; varsayilan ayarlar kullanilacak (docs\setup.md adim 2)"
}

$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute $python -Argument "-m ko_monitor run" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
# Screen capture needs the user's desktop session, so the task runs interactively as this user.
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description "KO Monitor: oyun izleme ajani ve telefon API'si" -Force | Out-Null

Write-Host "Gorev kaydedildi: $TaskName"
Write-Host "Hemen baslatmak icin: Start-ScheduledTask -TaskName '$TaskName'"
```

Bu adımda script **çalıştırılmaz**; yalnızca Step 5'teki test sözdizimini ayrıştırır.

- [ ] **Step 4: Kurulum belgesini yaz**

`docs/setup.md`:
````markdown
# KO Monitor — Kurulum

Bu belge bilgisayarda ajanın kurulmasını, dışarıdan canlılık kontrolünü, telefondan erişimi ve iPhone uygulamasının kurulmasını anlatır. Hesap açma, oturum açma ve sistem ayarı değiştiren adımları **sen** yaparsın; hiçbir şifre bu projeye yazılmaz.

## 1. Python ortamı

PowerShell'de proje klasöründe (`C:\Users\Serdar\Desktop\ko-monitor`):

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv   # yalnızca .venv yoksa
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q
```

Testler geçmeli.

## 2. `config.toml`

```powershell
Copy-Item config.example.toml config.toml
notepad config.toml
```

- `[push] contact`: `mailto:` ile kendi e-posta adresin (Web Push servisleri iletişim için ister).
- `[api] port`: varsayılan `8765`. Değiştirirsen aşağıdaki `tailscale serve` komutunda da aynı portu kullan.
- `[api] stream_quality`: telefonda kalite seçilmediğinde canlı yayın kalitesi (`low` / `medium` / `high`).
- `[heartbeat]`: 3. adımda doldurulur.

`config.toml` ve `data\` git'e girmez. `data\vapid_private.pem` ilk çalıştırmada oluşur; silersen telefonda Ayarlar → **Bildirimleri aç**'a yeniden dokunman gerekir.

## 3. Dış canlılık kontrolü: healthchecks.io + ntfy

Bilgisayar, internet ya da ajan çökerse ajan kendi bildirimini atamaz; bu durumda healthchecks.io haber verir.

1. iPhone'a App Store'dan **ntfy** uygulamasını kur. Uygulamada tahmin edilmesi zor bir konu (topic) adına abone ol, ör. `ko-monitor-<rastgele harfler>`.
2. https://healthchecks.io adresinde hesap aç (ücretsiz plan yeterli).
3. **Add Check**: Period **1 minute**, Grace **3 minutes**. Oluşan **ping URL**'ini (`https://hc-ping.com/<uuid>`) `config.toml` → `[heartbeat] ping_url` alanına yaz.
4. Project → **Settings** → **API Keys** → okuma-yazma (read-write) anahtar oluştur → `[heartbeat] api_key`. (Oyunu kapattığında ajan kontrolü bu anahtarla duraklatır; oyun yeniden açılınca ilk ping kontrolü kendiliğinden etkinleştirir.)
5. **Integrations** → **ntfy** → sunucu `https://ntfy.sh`, konu: 1. adımdaki konu adı → kaydet → **Test** ile iPhone'da ntfy bildirimi geldiğini gör.

## 4. İlk çalıştırma (elle)

```powershell
.venv\Scripts\python.exe -m ko_monitor run
```

Bilgisayarın tarayıcısında `http://127.0.0.1:8765` açılır: Durum ekranı görünmeli. Sunucu yalnızca `127.0.0.1`'de dinler; ev ağından (LAN) erişilemez. Durdurmak için Ctrl+C.

## 5. Telefondan erişim: Tailscale

1. Bilgisayara https://tailscale.com/download adresinden Tailscale'i kur ve oturum aç.
2. iPhone'a App Store'dan **Tailscale**'i kur, **aynı hesapla** oturum aç, VPN'i aç.
3. Tailscale yönetim panelinde (https://login.tailscale.com/admin/dns) **MagicDNS** ve **HTTPS Certificates** açık olmalı (Web Push ve PWA geçerli HTTPS ister).
4. Ajan çalışırken bilgisayarda:
   ```powershell
   tailscale serve --bg 8765
   tailscale serve status
   ```
   `status` çıktısındaki adresi not al: `https://<bilgisayar-adı>.<tailnet>.ts.net`. Bu adres yalnızca senin Tailscale cihazlarından açılır; ek şifre yoktur.
   Yayını kaldırmak için: `tailscale serve reset`.

## 6. iPhone uygulaması (PWA) ve bildirimler

Gereken: **iOS 16.4** veya üstü. Web Push iPhone'da yalnızca ana ekrana eklenmiş uygulamada çalışır.

1. iPhone'da Tailscale VPN açıkken **Safari** ile 5. adımdaki `https://...ts.net` adresini aç.
2. **Paylaş** düğmesi → **Ana Ekrana Ekle** → **Ekle**.
3. Ana ekrandaki **KO Monitor** simgesiyle uygulamayı aç (Safari sekmesinden değil).
4. **Ayarlar** → **Bildirimleri aç** → çıkan izin isteğinde **İzin Ver**.
5. **Test bildirimi gönder** → birkaç saniye içinde "🔔 Test bildirimi" gelmeli; dokununca uygulama Olaylar ekranında açılır.
6. **Canlı** sekmesi: görüntü kendiliğinden başlar; Düşük / Orta / Yüksek ile kalite seçilir; telefonu yan çevirince tam ekran olur. Uygulamadan çıkınca yayın durur.

Bildirimler Apple push servisi üzerinden gelir: telefonun o anda Tailscale'e bağlı olması gerekmez. Uygulamayı açıp durum/canlı görüntü görmek için Tailscale VPN açık olmalı (Tailscale uygulamasında "VPN On Demand" ile hep açık tutulabilir).

## 7. Otomatik başlatma (Görev Zamanlayıcı)

Elle çalışan ajanı (4. adım) Ctrl+C ile kapat; aynı anda iki kopya çalışırsa ikincisi port dolu olduğu için kapanır.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
Start-ScheduledTask -TaskName "KO Monitor"
Get-ScheduledTask -TaskName "KO Monitor" | Get-ScheduledTaskInfo
Get-Content logs\agent.log -Tail 20
```

Görev oturum açılışında başlar, konsol penceresi açmaz (`pythonw.exe`) ve hata ile biterse 1 dakikada bir yeniden başlatılır. Günlük: `logs\agent.log`.

- Durdurmak: `Stop-ScheduledTask -TaskName "KO Monitor"`
- Kaldırmak: `Unregister-ScheduledTask -TaskName "KO Monitor" -Confirm:$false`

`tailscale serve --bg` ayarı Tailscale tarafından saklanır; bilgisayar yeniden başlayınca tekrar çalıştırman gerekmez.

## 8. Sorun giderme

| Belirti | Kontrol |
|---|---|
| Telefonda sayfa açılmıyor | iPhone'da Tailscale VPN açık mı? Bilgisayarda `tailscale serve status` adresi gösteriyor mu? Ajan çalışıyor mu (`logs\agent.log`)? |
| "Bildirimleri aç" izin sormuyor | Uygulama ana ekran simgesinden mi açıldı? iOS 16.4+ mı? iPhone Ayarlar → Bildirimler → KO Monitor. |
| Test bildirimi "Gönderilemedi" | `logs\agent.log` içindeki `push failed` satırları; bilgisayarın internet bağlantısı. |
| Canlı ekranda "Oyun penceresi küçültülmüş" | Oyun penceresi simge durumunda; Windows küçültülmüş pencereden görüntü vermez. |
| Durum "Son güncelleme" sürekli eskiyor | Ajan döngüsü durmuş olabilir; görev yeniden başlatılır, `logs\agent.log`'a bak. |
| healthchecks.io'dan yanlış alarm | Oyun kapatılınca kontrol duraklatılır; `[heartbeat] api_key` doğru mu? |
````

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_scripts.py -q`
Expected: `4 passed`

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: tümü PASS (örneği olmayan kalibrasyon kategorileri SKIPPED)

- [ ] **Step 6: Commit**

```powershell
git add scripts/install-autostart.ps1 docs/setup.md tests/test_scripts.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "docs: setup guide and task scheduler autostart script" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Kullanıcıya devret (uygulayıcı çalıştırmaz)**

Kullanıcıya şu listeyi ilet; her biri kullanıcının kendi yapacağı adımdır:
1. `docs/setup.md` adım 2-3: `config.toml`, healthchecks.io kontrolü, API anahtarı, ntfy entegrasyonu.
2. Adım 5: Tailscale kurulumu/oturum açma ve `tailscale serve --bg 8765`.
3. Adım 6: iPhone'da Ana Ekrana Ekle → Bildirimleri aç → Test bildirimi gönder → Canlı ekranı yatay çevirme kontrolü (spec §9: iPhone'da elle push ve canlı ekran testi).
4. Adım 7: `scripts\install-autostart.ps1` çalıştırma.

---

## Plan 2 sonrası

Bu plan bittiğinde spec'in 4-6. uygulama adımları tamamlanır: telefondan durum, geçmiş, olaylar ve canlı görüntü; Web Push bildirimleri; Tailscale ile erişim ve oturum açılışında otomatik başlatma. Sonradan eklenebilecekler (spec §11): Pushover notifier, birden fazla client.
