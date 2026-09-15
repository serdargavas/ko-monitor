# KO Monitor – Plan 1: Ajan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Knight Evolution oyun penceresini ekrandan okuyup ölüm / envanter dolu / disconnect / donma / kör / oyun kapandı olaylarını tespit eden, olayları ve dakikalık durum kayıtlarını SQLite'a yazan, Web Push ve healthchecks.io ile haber veren Windows Python ajanı.

**Architecture:** Tek süreç. `capture` (Windows Graphics Capture) → `detectors` (RapidOCR + OpenCV, `calibration.json` ile yönlendirilir) → `monitor` (saf durum makinesi, `Readings` → `Event`) → `storage` / `notifier` / `heartbeat`. `agent.py` bunları 2 sn'lik döngüde birleştirir; `--replay` kayıtlı karelerle oyunsuz çalışır. API ve PWA bu planda yok (Plan 2).

**Tech Stack:** Python 3.12, windows-capture 2.0.1, RapidOCR 3.9.2 + onnxruntime, opencv-python, numpy, psutil, pywebpush 2.5.0, py-vapid 1.9.4, httpx, pytest.

**Spec:** `docs/superpowers/specs/2026-09-15-ko-monitor-design.md`

## Global Constraints

- Salt okuma: oyuna tuş/tıklama göndermek, bellek okumak, paket dinlemek YASAK.
- Python `>=3.12`; yorumlayıcı: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`; sanal ortam `.venv`.
- Süreç adı `Client.acme`, pencere başlığı `Knight Evolution`, çözünürlük 2560x1440, UI ölçeği 1.0.
- Varsayılan süreler: hızlı kontrol 2 sn, kapalıyken 10 sn, snapshot 60 sn, onay 2 okuma, dolaylı disconnect 15 sn, donma 120 sn, kör 60 sn, envanter dolu tekrarı 600 sn; bildirim en fazla 300 sn eski olabilir; snapshot saklama 30 gün.
- Öncelik: Kapalı > Kör > Disconnect > Ölü > Donmuş > Canlı. Donmuş yalnızca Canlı/Donmuş durumdayken değerlendirilir. Kör onaylanana kadar mevcut durum korunur.
- Kötü durumdan çıkış olumlu okuma ister (Ölü→Canlı: `hp > 0`; Disconnect→Canlı: HUD görünür). `None` durumu değiştirmez.
- Yalnızca kötü duruma girişte ve `GAME_CLOSED`/`INVENTORY_FULL`'da `notify=True`.
- Zaman damgaları `time.time()` (unix saniye, float).
- Gizli/yerel dosyalar git'e girmez: `config.toml`, `data/`, `logs/`, `.venv/`.
- Kod ve kod yorumları İngilizce; kullanıcıya görünen bildirim metinleri Türkçe.
- Komutlar PowerShell'de, proje kökünden (`C:\Users\Serdar\Desktop\ko-monitor`) çalıştırılır. Testler: `.venv\Scripts\python.exe -m pytest -q`.
- Git kimliği global tanımlı değil; commit komutları `git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit ...` biçimindedir ve mesaj sonunda `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` satırı bulunur.

## File Structure

```
ko-monitor/
  pyproject.toml              # package + deps + pytest config
  .gitignore
  config.example.toml         # documented config; user copies to config.toml
  calibration.json            # ROIs, templates, chat phrases (data, not code)
  templates/                  # template PNGs cut during calibration (Task 10)
  samples/<label>/*.png       # labeled real frames = test data
  src/ko_monitor/
    __init__.py
    __main__.py               # python -m ko_monitor → cli.main()
    cli.py                    # argparse: run, snap, record, ocr, crop, detect, vapid
    config.py                 # config.toml → Config dataclasses
    logging_setup.py          # rotating file + console logging
    models.py                 # State, CaptureStatus, EventKind, Readings, Event, Snapshot
    storage.py                # SQLite: snapshots, events, push_subscriptions
    process_watch.py          # is Client.acme running
    capture.py                # FrameSource protocol, WgcCapture, ReplaySource, is_black
    calibration.py            # calibration.json → Calibration; crop()
    ocr.py                    # RapidOCR wrapper: read_line (rec-only), read_block (det+rec)
    detectors/
      __init__.py             # Detector: frame → Readings
      hud.py                  # HP ratio + zone
      chat.py                 # ChatTracker (new lines) + phrase classification
      templates.py            # template_present()
      inventory.py            # inventory window, money, used slots
      frame_diff.py           # FrameDiff for frozen detection
    monitor.py                # Observation → state machine → Events; snapshot()
    messages.py               # Event → Turkish push payload
    vapid.py                  # VAPID key file + application server key
    notifier.py               # Notifier protocol, WebPushNotifier, PrintNotifier
    heartbeat.py              # healthchecks.io ping / pause
    agent.py                  # Agent.tick()/run(), build_agent()
  tests/
    conftest.py               # shared fixtures (real OCR engine, sample paths)
    test_*.py
```

---

### Task 1: Proje iskeleti, ayarlar ve loglama

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `config.example.toml`
- Create: `src/ko_monitor/__init__.py`, `src/ko_monitor/config.py`, `src/ko_monitor/logging_setup.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: —
- Produces: `load_config(path: Path | None) -> Config`; `Config(process_name, window_title, data_dir, log_dir, calibration_path, thresholds: Thresholds, push: PushConfig, heartbeat: HeartbeatConfig)`; `Thresholds(tick_s, closed_poll_s, snapshot_s, confirm_reads, disconnect_soft_s, frozen_s, blind_s, inventory_full_repeat_s, frozen_diff_max, snapshot_retention_s)`; `PushConfig(contact, max_age_s)`; `HeartbeatConfig(ping_url, api_key)`; `setup_logging(log_dir: Path) -> None`.

- [ ] **Step 1: Paketleme dosyalarını oluştur**

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "ko-monitor"
version = "0.1.0"
requires-python = ">=3.12"
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
]

[project.optional-dependencies]
dev = ["pytest>=9.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["ocr: uses the real RapidOCR model (slower)"]
```

`.gitignore`:
```
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
config.toml
data/
logs/
```

`src/ko_monitor/__init__.py`:
```python
"""KO Monitor: read-only screen monitor for the Knight Evolution client."""
```

- [ ] **Step 2: Sanal ortamı kur**

Run:
```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```
Expected: `Successfully installed ... ko-monitor-0.1.0 ...`

- [ ] **Step 3: Failing test yaz**

`tests/test_config.py`:
```python
from pathlib import Path

from ko_monitor.config import load_config


def test_defaults_when_file_missing(tmp_path: Path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.process_name == "Client.acme"
    assert cfg.window_title == "Knight Evolution"
    assert cfg.thresholds.tick_s == 2.0
    assert cfg.thresholds.disconnect_soft_s == 15.0
    assert cfg.heartbeat.ping_url == ""


def test_none_path_gives_defaults():
    assert load_config(None).thresholds.blind_s == 60.0


def test_overrides_are_merged_with_defaults(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[general]\nwindow_title = "Other"\ndata_dir = "D:/kodata"\n'
        "[thresholds]\nfrozen_s = 30\n"
        '[heartbeat]\nping_url = "https://hc-ping.com/abc"\n',
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.window_title == "Other"
    assert cfg.data_dir == Path("D:/kodata")
    assert cfg.thresholds.frozen_s == 30
    assert cfg.thresholds.blind_s == 60.0
    assert cfg.heartbeat.ping_url == "https://hc-ping.com/abc"
    assert cfg.push.max_age_s == 300.0
```

- [ ] **Step 4: Testin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.config'`

- [ ] **Step 5: `config.py` yaz**

`src/ko_monitor/config.py`:
```python
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Thresholds:
    tick_s: float = 2.0
    closed_poll_s: float = 10.0
    snapshot_s: float = 60.0
    confirm_reads: int = 2
    disconnect_soft_s: float = 15.0
    frozen_s: float = 120.0
    blind_s: float = 60.0
    inventory_full_repeat_s: float = 600.0
    frozen_diff_max: float = 0.5
    snapshot_retention_s: float = 30 * 86400


@dataclass(frozen=True)
class PushConfig:
    contact: str = "mailto:you@example.com"
    max_age_s: float = 300.0


@dataclass(frozen=True)
class HeartbeatConfig:
    ping_url: str = ""
    api_key: str = ""


@dataclass(frozen=True)
class Config:
    process_name: str = "Client.acme"
    window_title: str = "Knight Evolution"
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    calibration_path: Path = Path("calibration.json")
    thresholds: Thresholds = field(default_factory=Thresholds)
    push: PushConfig = field(default_factory=PushConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)


def load_config(path: Path | None) -> Config:
    if path is None or not path.exists():
        return Config()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    general = raw.get("general", {})
    defaults = Config()
    return Config(
        process_name=general.get("process_name", defaults.process_name),
        window_title=general.get("window_title", defaults.window_title),
        data_dir=Path(general.get("data_dir", defaults.data_dir)),
        log_dir=Path(general.get("log_dir", defaults.log_dir)),
        calibration_path=Path(general.get("calibration_path", defaults.calibration_path)),
        thresholds=Thresholds(**raw.get("thresholds", {})),
        push=PushConfig(**raw.get("push", {})),
        heartbeat=HeartbeatConfig(**raw.get("heartbeat", {})),
    )
```

- [ ] **Step 6: Testin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -q`
Expected: `3 passed`

- [ ] **Step 7: Örnek ayar dosyası ve loglama**

`config.example.toml`:
```toml
# Copy to config.toml and edit. config.toml is not committed.

[general]
process_name = "Client.acme"
window_title = "Knight Evolution"
data_dir = "data"
log_dir = "logs"
calibration_path = "calibration.json"

[thresholds]
tick_s = 2.0                   # fast check interval while the game is open
closed_poll_s = 10.0           # process check interval while the game is closed
snapshot_s = 60.0              # health check / snapshot interval
confirm_reads = 2              # consecutive reads for death and explicit disconnect
disconnect_soft_s = 15.0       # HUD missing this long -> disconnected
frozen_s = 120.0               # no picture change this long -> frozen
blind_s = 60.0                 # capture unusable this long -> blind
inventory_full_repeat_s = 600.0
frozen_diff_max = 0.5          # mean abs diff (0-255) of 64x36 gray frames counted as "no change"
snapshot_retention_s = 2592000 # 30 days

[push]
contact = "mailto:you@example.com"  # VAPID contact; use your own address
max_age_s = 300.0

[heartbeat]
ping_url = ""   # e.g. https://hc-ping.com/<uuid>; empty disables heartbeat
api_key = ""    # healthchecks.io project API key, needed to pause the check
```

`src/ko_monitor/logging_setup.py`:
```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "agent.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers[:] = [file_handler, console]
```

- [ ] **Step 8: Commit**

```powershell
git add pyproject.toml .gitignore config.example.toml src tests
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: project skeleton, config loader and logging" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Modeller ve SQLite kayıt

**Files:**
- Create: `src/ko_monitor/models.py`, `src/ko_monitor/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `State` (StrEnum): `CLOSED="closed"`, `ALIVE="alive"`, `DEAD="dead"`, `DISCONNECTED="disconnected"`, `FROZEN="frozen"`, `BLIND="blind"`
  - `CaptureStatus` (StrEnum): `OK`, `MINIMIZED`, `NOT_FOUND`, `BLACK`
  - `EventKind` (StrEnum): `GAME_STARTED`, `GAME_CLOSED`, `DEAD`, `DISCONNECTED`, `FROZEN`, `BLIND`, `RECOVERED`, `INVENTORY_FULL`
  - `Readings` dataclass (fields below), `Event(kind, ts, detail="", notify=False)`, `Snapshot(ts, state, hp, hp_max, zone, money_last, slots_used_last, slots_total_last, inventory_seen_at)`
  - `Storage(path: Path)` with `add_snapshot(Snapshot)`, `snapshots_since(ts) -> list[Snapshot]`, `prune_snapshots(older_than: float) -> int`, `add_event(Event) -> int`, `mark_notified(event_id: int, at: float)`, `recent_events(limit=50) -> list[dict]`, `add_subscription(endpoint: str, keys: dict, now: float)`, `subscriptions() -> list[dict]` (each `{"endpoint": str, "keys": dict}`), `delete_subscription(endpoint: str)`, `close()`

- [ ] **Step 1: Modelleri yaz** (davranışsız veri tipleri; storage testleriyle birlikte test edilir)

`src/ko_monitor/models.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class State(StrEnum):
    CLOSED = "closed"
    ALIVE = "alive"
    DEAD = "dead"
    DISCONNECTED = "disconnected"
    FROZEN = "frozen"
    BLIND = "blind"


class CaptureStatus(StrEnum):
    OK = "ok"
    MINIMIZED = "minimized"
    NOT_FOUND = "not_found"
    BLACK = "black"


class EventKind(StrEnum):
    GAME_STARTED = "game_started"
    GAME_CLOSED = "game_closed"
    DEAD = "dead"
    DISCONNECTED = "disconnected"
    FROZEN = "frozen"
    BLIND = "blind"
    RECOVERED = "recovered"
    INVENTORY_FULL = "inventory_full"


@dataclass
class Readings:
    """What the detectors saw on one frame. None means 'could not tell'."""

    hud_visible: bool = False
    hp: int | None = None
    hp_max: int | None = None
    zone: str | None = None
    revive_dialog: bool | None = None
    login_screen: bool | None = None
    disconnect_dialog: bool | None = None
    chat_events: list[str] = field(default_factory=list)
    inventory_open: bool | None = None
    money: int | None = None
    slots_used: int | None = None
    slots_total: int | None = None
    frame_diff: float | None = None


@dataclass(frozen=True)
class Event:
    kind: EventKind
    ts: float
    detail: str = ""
    notify: bool = False


@dataclass(frozen=True)
class Snapshot:
    ts: float
    state: State
    hp: int | None
    hp_max: int | None
    zone: str | None
    money_last: int | None
    slots_used_last: int | None
    slots_total_last: int | None
    inventory_seen_at: float | None
```

- [ ] **Step 2: Failing test yaz**

`tests/test_storage.py`:
```python
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
```

- [ ] **Step 3: Testin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_storage.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.storage'`

- [ ] **Step 4: `storage.py` yaz**

`src/ko_monitor/storage.py`:
```python
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from ko_monitor.models import Event, Snapshot, State

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots(
  ts REAL NOT NULL,
  state TEXT NOT NULL,
  hp INTEGER, hp_max INTEGER, zone TEXT,
  money_last INTEGER, slots_used_last INTEGER, slots_total_last INTEGER,
  inventory_seen_at REAL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  kind TEXT NOT NULL,
  detail TEXT NOT NULL,
  notified INTEGER NOT NULL DEFAULT 0,
  notified_at REAL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS push_subscriptions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint TEXT NOT NULL UNIQUE,
  keys_json TEXT NOT NULL,
  created_at REAL NOT NULL
);
"""


class Storage:
    """SQLite access. Thread-safe so the API (Plan 2) can share it with the agent loop."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def add_snapshot(self, s: Snapshot) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?,?)",
                (s.ts, s.state.value, s.hp, s.hp_max, s.zone, s.money_last,
                 s.slots_used_last, s.slots_total_last, s.inventory_seen_at),
            )

    def snapshots_since(self, ts: float) -> list[Snapshot]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM snapshots WHERE ts >= ? ORDER BY ts", (ts,)
            ).fetchall()
        return [
            Snapshot(r["ts"], State(r["state"]), r["hp"], r["hp_max"], r["zone"],
                     r["money_last"], r["slots_used_last"], r["slots_total_last"],
                     r["inventory_seen_at"])
            for r in rows
        ]

    def prune_snapshots(self, older_than: float) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM snapshots WHERE ts < ?", (older_than,))
        return cur.rowcount

    def add_event(self, e: Event) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO events(ts, kind, detail) VALUES (?,?,?)",
                (e.ts, e.kind.value, e.detail),
            )
        return int(cur.lastrowid)

    def mark_notified(self, event_id: int, at: float) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE events SET notified = 1, notified_at = ? WHERE id = ?", (at, event_id)
            )

    def recent_events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY ts DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"id": r["id"], "ts": r["ts"], "kind": r["kind"], "detail": r["detail"],
             "notified": bool(r["notified"]), "notified_at": r["notified_at"]}
            for r in rows
        ]

    def add_subscription(self, endpoint: str, keys: dict, now: float) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO push_subscriptions(endpoint, keys_json, created_at) VALUES (?,?,?) "
                "ON CONFLICT(endpoint) DO UPDATE SET keys_json = excluded.keys_json",
                (endpoint, json.dumps(keys), now),
            )

    def subscriptions(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT endpoint, keys_json FROM push_subscriptions ORDER BY id"
            ).fetchall()
        return [{"endpoint": r["endpoint"], "keys": json.loads(r["keys_json"])} for r in rows]

    def delete_subscription(self, endpoint: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
```

- [ ] **Step 5: Testin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_storage.py -q`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/ko_monitor/models.py src/ko_monitor/storage.py tests/test_storage.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: domain models and SQLite storage" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Süreç kontrolü, ekran yakalama ve `snap` / `record` komutları

**Files:**
- Create: `src/ko_monitor/process_watch.py`, `src/ko_monitor/capture.py`, `src/ko_monitor/cli.py`, `src/ko_monitor/__main__.py`
- Test: `tests/test_process_watch.py`, `tests/test_capture.py`

**Interfaces:**
- Consumes: `CaptureStatus` (Task 2), `load_config`, `Config` (Task 1)
- Produces:
  - `is_process_running(name: str, processes: Iterable | None = None) -> bool`
  - `FrameSource` Protocol: `latest() -> tuple[CaptureStatus, np.ndarray | None]` (frame is BGR `uint8` HxWx3), `close() -> None`
  - `is_black(frame: np.ndarray, threshold: float = 0.95) -> bool`
  - `ReplaySource(folder: Path)` (FrameSource) + `exhausted: bool` property
  - `WgcCapture(window_title: str, black_threshold: float = 0.95)` (FrameSource)
  - `cli.main(argv: list[str] | None = None) -> int`; subcommands `snap LABEL`, `record LABEL --seconds N --interval S`

- [ ] **Step 1: Failing testleri yaz**

`tests/test_process_watch.py`:
```python
from types import SimpleNamespace

import psutil

from ko_monitor.process_watch import is_process_running


class Denied:
    @property
    def info(self):
        raise psutil.AccessDenied(pid=1)


def procs(*names):
    return [SimpleNamespace(info={"name": n}) for n in names]


def test_finds_process_case_insensitively():
    assert is_process_running("Client.acme", procs("explorer.exe", "client.ACME"))


def test_missing_process():
    assert not is_process_running("Client.acme", procs("explorer.exe", None))


def test_skips_processes_it_cannot_read():
    assert is_process_running("Client.acme", [Denied(), *procs("Client.acme")])
```

`tests/test_capture.py`:
```python
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.capture import ReplaySource, is_black
from ko_monitor.models import CaptureStatus


def test_is_black():
    assert is_black(np.zeros((1440, 2560, 3), np.uint8))
    frame = np.zeros((1440, 2560, 3), np.uint8)
    frame[:, :400] = 120  # ~16% bright pixels
    assert not is_black(frame)


def test_replay_serves_files_in_name_order_then_repeats_last(tmp_path: Path):
    for name, value in (("b.png", 200), ("a.png", 100)):
        cv2.imwrite(str(tmp_path / name), np.full((20, 30, 3), value, np.uint8))
    source = ReplaySource(tmp_path)
    status, first = source.latest()
    assert status == CaptureStatus.OK and first[0, 0, 0] == 100
    assert not source.exhausted
    _, second = source.latest()
    assert second[0, 0, 0] == 200
    assert source.exhausted
    _, again = source.latest()
    assert again[0, 0, 0] == 200


def test_replay_marks_black_frames(tmp_path: Path):
    cv2.imwrite(str(tmp_path / "x.png"), np.zeros((20, 30, 3), np.uint8))
    assert ReplaySource(tmp_path).latest()[0] == CaptureStatus.BLACK


def test_replay_requires_frames(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ReplaySource(tmp_path)
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_process_watch.py tests/test_capture.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.process_watch'`

- [ ] **Step 3: `process_watch.py` yaz**

`src/ko_monitor/process_watch.py`:
```python
from __future__ import annotations

from collections.abc import Iterable

import psutil


def is_process_running(name: str, processes: Iterable | None = None) -> bool:
    target = name.lower()
    for proc in processes if processes is not None else psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == target:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False
```

- [ ] **Step 4: `capture.py` yaz**

`src/ko_monitor/capture.py`:
```python
from __future__ import annotations

import ctypes
import logging
import threading
import time
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from ko_monitor.models import CaptureStatus

log = logging.getLogger(__name__)


class FrameSource(Protocol):
    def latest(self) -> tuple[CaptureStatus, np.ndarray | None]: ...

    def close(self) -> None: ...


def is_black(frame: np.ndarray, threshold: float = 0.95) -> bool:
    sample = frame[::16, ::16, :3].astype(np.float32).mean(axis=2)
    return float((sample < 8).mean()) >= threshold


class ReplaySource:
    """Serves recorded PNG frames in file-name order, one per latest() call; repeats the last."""

    def __init__(self, folder: Path):
        self._files = sorted(folder.glob("*.png"))
        if not self._files:
            raise FileNotFoundError(f"no PNG frames in {folder}")
        self._index = 0

    @property
    def exhausted(self) -> bool:
        return self._index >= len(self._files)

    def latest(self) -> tuple[CaptureStatus, np.ndarray | None]:
        path = self._files[min(self._index, len(self._files) - 1)]
        self._index += 1
        frame = cv2.imread(str(path))
        if frame is None:
            return CaptureStatus.NOT_FOUND, None
        return (CaptureStatus.BLACK if is_black(frame) else CaptureStatus.OK), frame

    def close(self) -> None:
        pass


def find_window(title: str) -> int:
    return int(ctypes.windll.user32.FindWindowW(None, title) or 0)


def is_minimized(hwnd: int) -> bool:
    return bool(ctypes.windll.user32.IsIconic(hwnd))


class WgcCapture:
    """Windows Graphics Capture session on the game window; keeps only the newest frame.

    Works while the window is covered by other windows; a minimized window yields no frames.
    """

    def __init__(self, window_title: str, black_threshold: float = 0.95):
        self._title = window_title
        self._black_threshold = black_threshold
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._control = None
        self._retry_at = 0.0
        self._backoff = 1.0

    def _start(self) -> None:
        from windows_capture import Frame, InternalCaptureControl, WindowsCapture

        with self._lock:
            self._frame = None
        cap = WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            minimum_update_interval=250,
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
        log.info("capture session started for %r", self._title)

    def latest(self) -> tuple[CaptureStatus, np.ndarray | None]:
        hwnd = find_window(self._title)
        if not hwnd:
            self.close()
            return CaptureStatus.NOT_FOUND, None
        if is_minimized(hwnd):
            return CaptureStatus.MINIMIZED, None
        if self._control is None or self._control.is_finished():
            now = time.monotonic()
            if now < self._retry_at:
                return CaptureStatus.NOT_FOUND, None
            try:
                self._start()
                self._backoff = 1.0
            except Exception:
                log.exception("capture start failed; retrying in %.0fs", self._backoff)
                self._control = None
                self._retry_at = now + self._backoff
                self._backoff = min(self._backoff * 2, 30.0)
                return CaptureStatus.NOT_FOUND, None
        with self._lock:
            frame = self._frame
        if frame is None:
            return CaptureStatus.NOT_FOUND, None
        status = CaptureStatus.BLACK if is_black(frame, self._black_threshold) else CaptureStatus.OK
        return status, frame

    def close(self) -> None:
        if self._control is not None and not self._control.is_finished():
            self._control.stop()
        self._control = None
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_process_watch.py tests/test_capture.py -q`
Expected: `7 passed`

- [ ] **Step 6: CLI (`snap`, `record`) yaz**

`src/ko_monitor/__main__.py`:
```python
import sys

from ko_monitor.cli import main

sys.exit(main())
```

`src/ko_monitor/cli.py`:
```python
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2

from ko_monitor.capture import WgcCapture
from ko_monitor.config import Config, load_config


def _grab_one(cap: WgcCapture, timeout_s: float = 5.0):
    deadline = time.monotonic() + timeout_s
    status, frame = cap.latest()
    while frame is None and time.monotonic() < deadline:
        time.sleep(0.2)
        status, frame = cap.latest()
    return status, frame


def cmd_snap(args: argparse.Namespace, cfg: Config) -> int:
    cap = WgcCapture(cfg.window_title)
    try:
        status, frame = _grab_one(cap)
    finally:
        cap.close()
    if frame is None:
        print(f"Kare alınamadı: {status}")
        return 1
    out = Path("samples") / args.label / f"{datetime.now():%Y%m%d-%H%M%S}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), frame)
    print(out)
    return 0


def cmd_record(args: argparse.Namespace, cfg: Config) -> int:
    out_dir = Path("samples") / "replay" / args.label
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = WgcCapture(cfg.window_title)
    saved = 0
    try:
        _grab_one(cap)
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            status, frame = cap.latest()
            if frame is not None:
                saved += 1
                cv2.imwrite(str(out_dir / f"{saved:04d}.png"), frame)
            time.sleep(args.interval)
    finally:
        cap.close()
    print(f"{saved} kare -> {out_dir}")
    return 0 if saved else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ko_monitor")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snap", help="save the current game frame to samples/<label>/")
    snap.add_argument("label")
    snap.set_defaults(func=cmd_snap)

    record = sub.add_parser("record", help="save frames to samples/replay/<label>/ for replay")
    record.add_argument("label")
    record.add_argument("--seconds", type=float, default=30.0)
    record.add_argument("--interval", type=float, default=2.0)
    record.set_defaults(func=cmd_record)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args, load_config(args.config))
```

- [ ] **Step 7: Canlı oyunda elle doğrula** (oyun açık, küçültülmemiş)

Run: `.venv\Scripts\python.exe -m ko_monitor snap manual-check`
Expected: `samples\manual-check\<tarih>.png` yazdırılır. Dosyayı açınca oyun ekranı görünür (siyah değil).
Ardından: `Remove-Item -Recurse samples\manual-check`

- [ ] **Step 8: Tüm testler + commit**

Run: `.venv\Scripts\python.exe -m pytest -q` → Expected: `14 passed`
```powershell
git add src/ko_monitor/process_watch.py src/ko_monitor/capture.py src/ko_monitor/cli.py src/ko_monitor/__main__.py tests/test_process_watch.py tests/test_capture.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: process watch, window capture, snap and record commands" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Kalibrasyon dosyası, OCR sarmalayıcı ve HUD okuma (HP + bölge)

**Files:**
- Create: `calibration.json`, `src/ko_monitor/calibration.py`, `src/ko_monitor/ocr.py`, `src/ko_monitor/detectors/__init__.py` (boş docstring), `src/ko_monitor/detectors/hud.py`
- Create: `tests/conftest.py`, `tests/helpers.py`
- Add (zaten diskte): `samples/normal/spike-desktop.png`, `samples/normal/spike-wgc-visible.png`, `samples/normal/spike-wgc-covered.png` — spike'ta alınmış gerçek kareler; üçünde de HP `9718/9996`, bölge `Ronark Land (428, 506)`.
- Test: `tests/test_calibration.py`, `tests/test_hud.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `Roi = tuple[int, int, int, int]` (x, y, w, h)
  - `TemplateSpec(roi: Roi, file: Path, threshold: float)`
  - `InventorySpec(window: TemplateSpec, money_roi: Roi, slot_origin: tuple[int,int], slot_size: tuple[int,int], slot_step: tuple[int,int], cols: int, rows: int, empty_slot_file: Path, empty_max_diff: float)`
  - `Calibration(resolution: tuple[int,int], hp_roi, zone_roi, chat_roi: Roi, black_threshold: float, ocr_min_score: float, chat_phrases: dict[str, list[str]], templates: dict[str, TemplateSpec], inventory: InventorySpec | None)`; template anahtarları: `revive_dialog`, `login_screen`, `disconnect_dialog`
  - `load_calibration(path: Path) -> Calibration` (dosya yolları JSON dosyasının klasörüne göre çözülür; `chat_phrases` küçük harfe çevrilir)
  - `crop(frame: np.ndarray, roi: Roi) -> np.ndarray`
  - `OcrLine(text: str, score: float, box: Roi)`; `Ocr(min_score: float = 0.8)` with `read_line(image) -> tuple[str, float] | None` and `read_block(image) -> list[OcrLine]` (y'ye göre sıralı)
  - `parse_ratio(text: str) -> tuple[int, int] | None`, `parse_zone(text: str) -> str | None`, `read_hud(frame, calib, ocr) -> tuple[bool, int | None, int | None, str | None]` = `(hud_visible, hp, hp_max, zone)`
  - tests: fixtures `ocr`, `calib`; `helpers.sample_frames(label) -> list[Path]`, `helpers.ROOT`

- [ ] **Step 1: `calibration.json` oluştur** (ROI'ler spike karelerinde OCR kutularından ölçüldü: HP metni x=91-155, y=36-65; bölge metni x=57-183, y=76-91; chat alanı sağ alt)

`calibration.json`:
```json
{
  "resolution": [2560, 1440],
  "hp_roi": [60, 34, 130, 16],
  "zone_roi": [40, 74, 160, 20],
  "chat_roi": [1980, 960, 570, 410],
  "black_threshold": 0.95,
  "ocr_min_score": 0.8,
  "chat_phrases": {
    "inventory_full": []
  },
  "templates": {},
  "inventory": null
}
```

- [ ] **Step 2: Test yardımcılarını yaz**

`tests/helpers.py`:
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def sample_frames(label: str) -> list[Path]:
    return sorted((SAMPLES / label).glob("*.png"))
```

`tests/conftest.py`:
```python
import pytest

from helpers import ROOT


@pytest.fixture(scope="session")
def ocr():
    from ko_monitor.ocr import Ocr

    return Ocr(min_score=0.8)


@pytest.fixture(scope="session")
def calib():
    from ko_monitor.calibration import load_calibration

    return load_calibration(ROOT / "calibration.json")
```

- [ ] **Step 3: Failing testleri yaz**

`tests/test_calibration.py`:
```python
import json
from pathlib import Path

import numpy as np

from ko_monitor.calibration import crop, load_calibration


def test_repo_calibration_loads(calib):
    assert calib.resolution == (2560, 1440)
    assert calib.hp_roi == (60, 34, 130, 16)
    assert calib.templates == {}
    assert calib.inventory is None
    assert calib.chat_phrases == {"inventory_full": []}


def test_paths_resolve_relative_to_file_and_phrases_lowercase(tmp_path: Path):
    data = {
        "resolution": [2560, 1440],
        "hp_roi": [1, 2, 3, 4], "zone_roi": [1, 2, 3, 4], "chat_roi": [1, 2, 3, 4],
        "chat_phrases": {"inventory_full": ["Inventory Is FULL"]},
        "templates": {"revive_dialog": {"roi": [10, 20, 30, 40], "file": "templates/r.png", "threshold": 0.9}},
        "inventory": {
            "window": {"roi": [0, 0, 5, 5], "file": "templates/inv.png", "threshold": 0.8},
            "money_roi": [1, 1, 2, 2], "slot_origin": [100, 200], "slot_size": [40, 40],
            "slot_step": [45, 45], "cols": 7, "rows": 4,
            "empty_slot_file": "templates/empty.png", "empty_max_diff": 12,
        },
    }
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    c = load_calibration(path)
    assert c.black_threshold == 0.95 and c.ocr_min_score == 0.8
    assert c.chat_phrases == {"inventory_full": ["inventory is full"]}
    assert c.templates["revive_dialog"].file == tmp_path / "templates" / "r.png"
    assert c.templates["revive_dialog"].roi == (10, 20, 30, 40)
    assert c.inventory.cols * c.inventory.rows == 28
    assert c.inventory.empty_slot_file == tmp_path / "templates" / "empty.png"


def test_crop():
    frame = np.arange(100 * 200 * 3, dtype=np.uint32).reshape(100, 200, 3)
    part = crop(frame, (10, 20, 30, 40))
    assert part.shape == (40, 30, 3)
    assert (part[0, 0] == frame[20, 10]).all()
```

`tests/test_hud.py`:
```python
import cv2
import numpy as np
import pytest

from helpers import sample_frames
from ko_monitor.detectors.hud import parse_ratio, parse_zone, read_hud


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("9718/9996", (9718, 9996)),
        ("0/9996", (0, 9996)),
        ("O/9996", (0, 9996)),
        ("9718 / 9996", (9718, 9996)),
        ("10/5", None),
        ("5/0", None),
        ("Lv 83", None),
        ("", None),
    ],
)
def test_parse_ratio(text, expected):
    assert parse_ratio(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ronark Land (428, 506)", "Ronark Land"),
        ("Moradon(12,34)", "Moradon"),
        ("Ronark Land", "Ronark Land"),
        ("   ", None),
    ],
)
def test_parse_zone(text, expected):
    assert parse_zone(text) == expected


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("normal"), ids=lambda p: p.name)
def test_read_hud_on_real_frames(path, calib, ocr):
    frame = cv2.imread(str(path))
    assert read_hud(frame, calib, ocr) == (True, 9718, 9996, "Ronark Land")


@pytest.mark.ocr
def test_read_hud_on_blank_frame(calib, ocr):
    frame = np.zeros((1440, 2560, 3), np.uint8)
    assert read_hud(frame, calib, ocr) == (False, None, None, None)
```

- [ ] **Step 4: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_calibration.py tests/test_hud.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.calibration'`

- [ ] **Step 5: `calibration.py` yaz**

`src/ko_monitor/calibration.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

Roi = tuple[int, int, int, int]  # x, y, w, h


@dataclass(frozen=True)
class TemplateSpec:
    roi: Roi
    file: Path
    threshold: float


@dataclass(frozen=True)
class InventorySpec:
    window: TemplateSpec
    money_roi: Roi
    slot_origin: tuple[int, int]
    slot_size: tuple[int, int]
    slot_step: tuple[int, int]
    cols: int
    rows: int
    empty_slot_file: Path
    empty_max_diff: float


@dataclass(frozen=True)
class Calibration:
    resolution: tuple[int, int]
    hp_roi: Roi
    zone_roi: Roi
    chat_roi: Roi
    black_threshold: float
    ocr_min_score: float
    chat_phrases: dict[str, list[str]]
    templates: dict[str, TemplateSpec]
    inventory: InventorySpec | None


def load_calibration(path: Path) -> Calibration:
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent

    def template(d: dict) -> TemplateSpec:
        return TemplateSpec(tuple(d["roi"]), base / d["file"], float(d["threshold"]))

    inv = raw.get("inventory")
    inventory = None
    if inv is not None:
        inventory = InventorySpec(
            window=template(inv["window"]),
            money_roi=tuple(inv["money_roi"]),
            slot_origin=tuple(inv["slot_origin"]),
            slot_size=tuple(inv["slot_size"]),
            slot_step=tuple(inv["slot_step"]),
            cols=int(inv["cols"]),
            rows=int(inv["rows"]),
            empty_slot_file=base / inv["empty_slot_file"],
            empty_max_diff=float(inv["empty_max_diff"]),
        )
    return Calibration(
        resolution=tuple(raw["resolution"]),
        hp_roi=tuple(raw["hp_roi"]),
        zone_roi=tuple(raw["zone_roi"]),
        chat_roi=tuple(raw["chat_roi"]),
        black_threshold=float(raw.get("black_threshold", 0.95)),
        ocr_min_score=float(raw.get("ocr_min_score", 0.8)),
        chat_phrases={k: [p.lower() for p in v] for k, v in raw.get("chat_phrases", {}).items()},
        templates={k: template(v) for k, v in raw.get("templates", {}).items()},
        inventory=inventory,
    )


def crop(frame: np.ndarray, roi: Roi) -> np.ndarray:
    x, y, w, h = roi
    return frame[y : y + h, x : x + w]
```

- [ ] **Step 6: `ocr.py` yaz**

Not: RapidOCR çağrısında `use_det` her seferinde açıkça verilmeli; spike'ta verilmediğinde bir önceki çağrının modu kullanıldı.

`src/ko_monitor/ocr.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ko_monitor.calibration import Roi


@dataclass(frozen=True)
class OcrLine:
    text: str
    score: float
    box: Roi


class Ocr:
    """RapidOCR wrapper. Not thread-safe: use from the agent loop thread only."""

    def __init__(self, min_score: float = 0.8):
        from rapidocr import RapidOCR

        self._engine = RapidOCR()
        self._min_score = min_score

    def read_line(self, image: np.ndarray) -> tuple[str, float] | None:
        """Recognition only (~15 ms). The image must contain a single line of text."""
        result = self._engine(image, use_det=False, use_cls=False, use_rec=True)
        if not result.txts:
            return None
        text, score = result.txts[0], float(result.scores[0])
        return (text, score) if score >= self._min_score else None

    def read_block(self, image: np.ndarray) -> list[OcrLine]:
        """Detection + recognition (~0.8 s for the chat area). Lines sorted top to bottom."""
        result = self._engine(image, use_det=True, use_cls=False, use_rec=True)
        if result.txts is None or result.boxes is None:
            return []
        lines = []
        for box, text, score in zip(result.boxes, result.txts, result.scores):
            if float(score) < self._min_score:
                continue
            xs = [int(p[0]) for p in box]
            ys = [int(p[1]) for p in box]
            lines.append(
                OcrLine(text, float(score), (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
            )
        lines.sort(key=lambda line: line.box[1])
        return lines
```

- [ ] **Step 7: HUD okuyucuyu yaz**

`src/ko_monitor/detectors/__init__.py`:
```python
"""Frame → Readings detectors."""
```

`src/ko_monitor/detectors/hud.py`:
```python
from __future__ import annotations

import re

import numpy as np

from ko_monitor.calibration import Calibration, crop
from ko_monitor.ocr import Ocr

_RATIO = re.compile(r"^(\d{1,7})/(\d{1,7})$")
_ZONE = re.compile(r"^(.*?)\s*\(\s*\d+\s*,\s*\d+\s*\)\s*$")
_DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "D": "0"})


def parse_ratio(text: str) -> tuple[int, int] | None:
    match = _RATIO.match(text.replace(" ", "").translate(_DIGIT_FIXES))
    if not match:
        return None
    current, maximum = int(match.group(1)), int(match.group(2))
    if maximum == 0 or current > maximum:
        return None
    return current, maximum


def parse_zone(text: str) -> str | None:
    text = text.strip()
    match = _ZONE.match(text)
    name = (match.group(1) if match else text).strip()
    return name or None


def read_hud(
    frame: np.ndarray, calib: Calibration, ocr: Ocr
) -> tuple[bool, int | None, int | None, str | None]:
    """Returns (hud_visible, hp, hp_max, zone). HUD counts as visible when HP text parses."""
    hp_line = ocr.read_line(crop(frame, calib.hp_roi))
    ratio = parse_ratio(hp_line[0]) if hp_line else None
    if ratio is None:
        return False, None, None, None
    zone_line = ocr.read_line(crop(frame, calib.zone_roi))
    zone = parse_zone(zone_line[0]) if zone_line else None
    return True, ratio[0], ratio[1], zone
```

- [ ] **Step 8: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_calibration.py tests/test_hud.py -q`
Expected: `19 passed` (calibration 3 + parse_ratio 8 + parse_zone 4 + gerçek kare 3 + boş kare 1)

`test_read_hud_on_real_frames` başarısız olursa assert farkındaki okunan metne bak; ROI metni kesiyorsa `hp_roi`/`zone_roi`'yi birkaç piksel genişlet (spike'ta ölçülen metin kutuları: HP x=91-155 y=36-48, bölge x=57-183 y=76-91).

- [ ] **Step 9: Commit**

```powershell
git add calibration.json src/ko_monitor/calibration.py src/ko_monitor/ocr.py src/ko_monitor/detectors tests/conftest.py tests/helpers.py tests/test_calibration.py tests/test_hud.py samples/normal
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: calibration file, OCR wrapper and HUD reader" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Chat okuyucu (yeni satırlar + ifade eşleme)

**Files:**
- Create: `src/ko_monitor/detectors/chat.py`
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `Calibration`, `crop` (Task 4), `Ocr.read_block` (Task 4)
- Produces:
  - `normalize(text: str) -> str` (küçük harf, tek boşluk)
  - `ChatTracker()` with `new_lines(lines: list[str]) -> list[str]` — ilk çağrı `[]` döner (ajan açıldığında ekrandaki eski mesajlar olay sayılmaz); sonrakiler yalnızca yeni (normalize edilmiş) satırları döner
  - `classify(lines: list[str], phrases: dict[str, list[str]]) -> list[str]` — eşleşen olay adları, tekrarsız, ilk görülme sırasıyla
  - `read_chat(frame, calib, ocr, tracker) -> list[str]`

- [ ] **Step 1: Failing test yaz**

`tests/test_chat.py`:
```python
import dataclasses

import cv2
import pytest

from helpers import SAMPLES
from ko_monitor.detectors.chat import ChatTracker, classify, normalize, read_chat


def test_normalize():
    assert normalize("  Picked  up 13468 Coins. ") == "picked up 13468 coins."


def test_first_read_is_history():
    assert ChatTracker().new_lines(["a", "b"]) == []


def test_scrolled_chat_returns_only_appended_lines():
    t = ChatTracker()
    t.new_lines(["a", "b", "c", "d"])
    assert t.new_lines(["c", "d", "e", "f"]) == ["e", "f"]


def test_unchanged_chat_returns_nothing():
    t = ChatTracker()
    t.new_lines(["a", "b"])
    assert t.new_lines(["a", "b"]) == []


def test_repeated_identical_message_counts_once_per_new_line():
    t = ChatTracker()
    t.new_lines(["x", "y", "350 SP Used"])
    assert t.new_lines(["y", "350 SP Used", "350 SP Used"]) == ["350 sp used"]


def test_no_overlap_falls_back_to_lines_not_seen_before():
    t = ChatTracker()
    t.new_lines(["a", "b"])
    assert t.new_lines(["b2", "a", "c"]) == ["b2", "c"]


def test_empty_chat_then_message():
    t = ChatTracker()
    t.new_lines([])
    assert t.new_lines(["Your inventory is full"]) == ["your inventory is full"]


def test_classify():
    phrases = {"inventory_full": ["inventory is full"], "coins": ["picked up"]}
    lines = ["picked up 5 coins.", "your inventory is full", "picked up 7 coins."]
    assert classify(lines, phrases) == ["coins", "inventory_full"]
    assert classify(["350 sp used"], phrases) == []


@pytest.mark.ocr
def test_read_chat_on_real_frames(calib, ocr):
    calib = dataclasses.replace(calib, chat_phrases={"coins": ["picked up"]})
    tracker = ChatTracker()
    first = cv2.imread(str(SAMPLES / "normal" / "spike-desktop.png"))
    second = cv2.imread(str(SAMPLES / "normal" / "spike-wgc-visible.png"))
    assert read_chat(first, calib, ocr, tracker) == []
    assert read_chat(second, calib, ocr, tracker) == ["coins"]
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_chat.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.detectors.chat'`

- [ ] **Step 3: `chat.py` yaz**

`src/ko_monitor/detectors/chat.py`:
```python
from __future__ import annotations

import numpy as np

from ko_monitor.calibration import Calibration, crop
from ko_monitor.ocr import Ocr


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


class ChatTracker:
    """Finds lines added since the previous read. Chat scrolls up: new lines appear at the bottom."""

    def __init__(self) -> None:
        self._prev: list[str] | None = None

    def new_lines(self, lines: list[str]) -> list[str]:
        current = [normalize(line) for line in lines]
        previous, self._prev = self._prev, current
        if previous is None:
            return []
        for k in range(min(len(previous), len(current)), 0, -1):
            if previous[-k:] == current[:k]:
                return current[k:]
        seen = set(previous)
        return [line for line in current if line not in seen]


def classify(lines: list[str], phrases: dict[str, list[str]]) -> list[str]:
    found: list[str] = []
    for line in lines:
        for kind, patterns in phrases.items():
            if kind not in found and any(p in line for p in patterns):
                found.append(kind)
    return found


def read_chat(frame: np.ndarray, calib: Calibration, ocr: Ocr, tracker: ChatTracker) -> list[str]:
    lines = [line.text for line in ocr.read_block(crop(frame, calib.chat_roi))]
    return classify(tracker.new_lines(lines), calib.chat_phrases)
```

- [ ] **Step 4: Testin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_chat.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/ko_monitor/detectors/chat.py tests/test_chat.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: chat reader with new-line tracking and phrase matching" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Şablon, envanter ve donma tespiti; `Detector`; kalibrasyon komutları

**Files:**
- Create: `src/ko_monitor/detectors/templates.py`, `src/ko_monitor/detectors/inventory.py`, `src/ko_monitor/detectors/frame_diff.py`
- Modify: `src/ko_monitor/detectors/__init__.py` (tam içerik aşağıda), `src/ko_monitor/cli.py` (tam içerik aşağıda; Task 3 sürümünün yerine)
- Test: `tests/test_templates.py`, `tests/test_inventory.py`, `tests/test_frame_diff.py`, `tests/test_detector.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `Calibration`, `TemplateSpec`, `InventorySpec`, `crop` (Task 4); `read_hud` (Task 4); `ChatTracker`, `read_chat` (Task 5); `Readings` (Task 2); `WgcCapture` (Task 3)
- Produces:
  - `load_template(path: str) -> np.ndarray | None` (önbellekli), `template_present(frame, spec: TemplateSpec | None) -> bool | None`
  - `parse_money(text: str) -> int | None`, `read_inventory(frame, spec: InventorySpec | None, ocr) -> tuple[bool | None, int | None, int | None, int | None]` = `(inventory_open, money, slots_used, slots_total)`
  - `FrameDiff()` with `update(frame) -> float | None`
  - `Detector(calib: Calibration, ocr: Ocr)` with `detect(frame) -> Readings | None` (çözünürlük uymazsa `None`)
  - CLI: `ocr IMAGE [--roi x,y,w,h]`, `crop IMAGE --roi x,y,w,h --out PATH`, `detect IMAGE...`; `parse_roi(text: str) -> tuple[int,int,int,int]`

- [ ] **Step 1: Failing testleri yaz**

`tests/test_templates.py`:
```python
from pathlib import Path

import cv2
import numpy as np

from ko_monitor.calibration import TemplateSpec
from ko_monitor.detectors.templates import template_present


def noisy_frame(seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 255, (300, 400, 3), dtype=np.uint8)


def write_template(tmp_path: Path, frame: np.ndarray) -> Path:
    path = tmp_path / "tpl.png"
    cv2.imwrite(str(path), frame[100:140, 200:260])
    return path


def test_present_inside_roi(tmp_path: Path):
    frame = noisy_frame()
    spec = TemplateSpec((180, 80, 120, 90), write_template(tmp_path, frame), 0.9)
    assert template_present(frame, spec) is True


def test_absent_elsewhere(tmp_path: Path):
    frame = noisy_frame()
    spec = TemplateSpec((0, 0, 150, 90), write_template(tmp_path, frame), 0.9)
    assert template_present(frame, spec) is False


def test_roi_smaller_than_template_is_absent(tmp_path: Path):
    frame = noisy_frame()
    spec = TemplateSpec((200, 100, 30, 20), write_template(tmp_path, frame), 0.9)
    assert template_present(frame, spec) is False


def test_unknown_when_not_calibrated(tmp_path: Path):
    frame = noisy_frame()
    assert template_present(frame, None) is None
    assert template_present(frame, TemplateSpec((0, 0, 10, 10), tmp_path / "missing.png", 0.9)) is None
```

`tests/test_inventory.py`:
```python
from pathlib import Path

import cv2
import numpy as np

from ko_monitor.calibration import InventorySpec, TemplateSpec
from ko_monitor.detectors.inventory import parse_money, read_inventory


class FakeOcr:
    def __init__(self, text: str | None):
        self.text = text

    def read_line(self, image):
        return None if self.text is None else (self.text, 0.99)


def test_parse_money():
    assert parse_money("1,234,567") == 1234567
    assert parse_money("12.500 Coins") == 12500
    assert parse_money("Coins") is None


def build(tmp_path: Path, with_window: bool = True):
    rng = np.random.default_rng(7)
    frame = np.full((300, 400, 3), 30, np.uint8)
    window = rng.integers(0, 255, (20, 60, 3), dtype=np.uint8)
    if with_window:
        frame[10:30, 10:70] = window
    empty = np.full((20, 20, 3), 50, np.uint8)
    empty[0, :] = empty[:, 0] = 90  # slot border
    for row in range(2):
        for col in range(2):
            frame[100 + row * 25 : 120 + row * 25, 100 + col * 25 : 120 + col * 25] = empty
    frame[100:120, 125:145] = rng.integers(0, 255, (20, 20, 3), dtype=np.uint8)  # item in slot (0,1)
    cv2.imwrite(str(tmp_path / "window.png"), window)
    cv2.imwrite(str(tmp_path / "empty.png"), empty)
    spec = InventorySpec(
        window=TemplateSpec((0, 0, 100, 50), tmp_path / "window.png", 0.9),
        money_roi=(200, 200, 80, 16),
        slot_origin=(100, 100), slot_size=(20, 20), slot_step=(25, 25), cols=2, rows=2,
        empty_slot_file=tmp_path / "empty.png", empty_max_diff=10.0,
    )
    return frame, spec


def test_not_calibrated():
    frame = np.zeros((10, 10, 3), np.uint8)
    assert read_inventory(frame, None, FakeOcr("1")) == (None, None, None, None)


def test_window_closed(tmp_path: Path):
    frame, spec = build(tmp_path, with_window=False)
    assert read_inventory(frame, spec, FakeOcr("1")) == (False, None, None, None)


def test_open_window_reads_money_and_slots(tmp_path: Path):
    frame, spec = build(tmp_path)
    assert read_inventory(frame, spec, FakeOcr("1,500,000")) == (True, 1500000, 1, 4)


def test_open_window_unreadable_money(tmp_path: Path):
    frame, spec = build(tmp_path)
    assert read_inventory(frame, spec, FakeOcr(None)) == (True, None, 1, 4)
```

`tests/test_frame_diff.py`:
```python
import numpy as np

from ko_monitor.detectors.frame_diff import FrameDiff


def test_frame_diff():
    diff = FrameDiff()
    a = np.zeros((1440, 2560, 3), np.uint8)
    b = np.full((1440, 2560, 3), 100, np.uint8)
    assert diff.update(a) is None
    assert diff.update(a) == 0.0
    assert diff.update(b) > 50
```

`tests/test_detector.py`:
```python
import cv2
import numpy as np
import pytest

from helpers import SAMPLES
from ko_monitor.detectors import Detector


@pytest.mark.ocr
def test_detect_real_frame(calib, ocr):
    detector = Detector(calib, ocr)
    frame = cv2.imread(str(SAMPLES / "normal" / "spike-desktop.png"))
    r = detector.detect(frame)
    assert (r.hud_visible, r.hp, r.hp_max, r.zone) == (True, 9718, 9996, "Ronark Land")
    assert (r.revive_dialog, r.login_screen, r.disconnect_dialog) == (None, None, None)
    assert (r.inventory_open, r.money, r.slots_used, r.slots_total) == (None, None, None, None)
    assert r.chat_events == []
    assert r.frame_diff is None
    assert detector.detect(frame).frame_diff == 0.0


@pytest.mark.ocr
def test_wrong_resolution_is_unreadable(calib, ocr):
    assert Detector(calib, ocr).detect(np.zeros((1080, 1920, 3), np.uint8)) is None
```

`tests/test_cli.py`:
```python
import argparse
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.cli import main, parse_roi


def test_parse_roi():
    assert parse_roi("1, 2,3,4") == (1, 2, 3, 4)
    with pytest.raises(argparse.ArgumentTypeError):
        parse_roi("1,2,3")


def test_crop_command(tmp_path: Path):
    image = tmp_path / "in.png"
    cv2.imwrite(str(image), np.zeros((100, 200, 3), np.uint8))
    out = tmp_path / "templates" / "out.png"
    assert main(["--config", str(tmp_path / "none.toml"), "crop", str(image), "--roi", "10,20,30,40", "--out", str(out)]) == 0
    assert cv2.imread(str(out)).shape == (40, 30, 3)
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_templates.py tests/test_inventory.py tests/test_frame_diff.py tests/test_detector.py tests/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError` (`ko_monitor.detectors.templates` vb.) ve `ImportError: cannot import name 'parse_roi'`

- [ ] **Step 3: `templates.py`, `inventory.py`, `frame_diff.py` yaz**

`src/ko_monitor/detectors/templates.py`:
```python
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from ko_monitor.calibration import TemplateSpec, crop


@lru_cache(maxsize=64)
def load_template(path: str) -> np.ndarray | None:
    if not Path(path).exists():
        return None
    return cv2.imread(path)


def template_present(frame: np.ndarray, spec: TemplateSpec | None) -> bool | None:
    """None = not calibrated (no spec or template file yet)."""
    if spec is None:
        return None
    template = load_template(str(spec.file))
    if template is None:
        return None
    region = crop(frame, spec.roi)
    if region.shape[0] < template.shape[0] or region.shape[1] < template.shape[1]:
        return False
    scores = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    return float(np.nan_to_num(scores).max()) >= spec.threshold
```

`src/ko_monitor/detectors/inventory.py`:
```python
from __future__ import annotations

import re

import cv2
import numpy as np

from ko_monitor.calibration import InventorySpec, crop
from ko_monitor.detectors.templates import load_template, template_present


def parse_money(text: str) -> int | None:
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def read_inventory(
    frame: np.ndarray, spec: InventorySpec | None, ocr
) -> tuple[bool | None, int | None, int | None, int | None]:
    """Returns (inventory_open, money, slots_used, slots_total); values only while the window is open."""
    if spec is None:
        return None, None, None, None
    is_open = template_present(frame, spec.window)
    if not is_open:
        return is_open, None, None, None

    money_line = ocr.read_line(crop(frame, spec.money_roi))
    money = parse_money(money_line[0]) if money_line else None

    empty = load_template(str(spec.empty_slot_file))
    if empty is None:
        return True, money, None, None
    used = 0
    width, height = spec.slot_size
    for row in range(spec.rows):
        for col in range(spec.cols):
            x = spec.slot_origin[0] + col * spec.slot_step[0]
            y = spec.slot_origin[1] + row * spec.slot_step[1]
            cell = frame[y : y + height, x : x + width]
            if cell.shape[:2] != empty.shape[:2]:
                cell = cv2.resize(cell, (empty.shape[1], empty.shape[0]))
            if float(cv2.absdiff(cell, empty).mean()) > spec.empty_max_diff:
                used += 1
    return True, money, used, spec.cols * spec.rows
```

`src/ko_monitor/detectors/frame_diff.py`:
```python
from __future__ import annotations

import cv2
import numpy as np


class FrameDiff:
    """Mean absolute difference (0-255) between consecutive frames, downscaled to 64x36 gray."""

    def __init__(self) -> None:
        self._prev: np.ndarray | None = None

    def update(self, frame: np.ndarray) -> float | None:
        small = cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        previous, self._prev = self._prev, gray
        if previous is None:
            return None
        return float(np.abs(gray - previous).mean())
```

- [ ] **Step 4: `Detector` yaz**

`src/ko_monitor/detectors/__init__.py`:
```python
"""Frame → Readings detectors."""

from __future__ import annotations

import numpy as np

from ko_monitor.calibration import Calibration
from ko_monitor.detectors.chat import ChatTracker, read_chat
from ko_monitor.detectors.frame_diff import FrameDiff
from ko_monitor.detectors.hud import read_hud
from ko_monitor.detectors.inventory import read_inventory
from ko_monitor.detectors.templates import template_present
from ko_monitor.models import Readings
from ko_monitor.ocr import Ocr


class Detector:
    """Stateful (chat history, previous frame): use one instance per frame stream."""

    def __init__(self, calib: Calibration, ocr: Ocr):
        self._calib = calib
        self._ocr = ocr
        self._chat = ChatTracker()
        self._diff = FrameDiff()

    def detect(self, frame: np.ndarray) -> Readings | None:
        height, width = frame.shape[:2]
        if (width, height) != self._calib.resolution:
            return None
        hud_visible, hp, hp_max, zone = read_hud(frame, self._calib, self._ocr)
        templates = self._calib.templates
        inventory_open, money, slots_used, slots_total = read_inventory(
            frame, self._calib.inventory, self._ocr
        )
        return Readings(
            hud_visible=hud_visible,
            hp=hp,
            hp_max=hp_max,
            zone=zone,
            revive_dialog=template_present(frame, templates.get("revive_dialog")),
            login_screen=template_present(frame, templates.get("login_screen")),
            disconnect_dialog=template_present(frame, templates.get("disconnect_dialog")),
            chat_events=read_chat(frame, self._calib, self._ocr, self._chat) if hud_visible else [],
            inventory_open=inventory_open,
            money=money,
            slots_used=slots_used,
            slots_total=slots_total,
            frame_diff=self._diff.update(frame),
        )
```

- [ ] **Step 5: `cli.py` dosyasını bu tam içerikle değiştir** (snap/record aynı; ocr/crop/detect eklendi)

`src/ko_monitor/cli.py`:
```python
from __future__ import annotations

import argparse
import dataclasses
import json
import time
from datetime import datetime
from pathlib import Path

import cv2

from ko_monitor.calibration import crop, load_calibration
from ko_monitor.capture import WgcCapture
from ko_monitor.config import Config, load_config


def parse_roi(text: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI must be x,y,w,h")
    return tuple(int(p) for p in parts)


def _read_image(path: Path):
    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"Görüntü okunamadı: {path}")
    return image


def _grab_one(cap: WgcCapture, timeout_s: float = 5.0):
    deadline = time.monotonic() + timeout_s
    status, frame = cap.latest()
    while frame is None and time.monotonic() < deadline:
        time.sleep(0.2)
        status, frame = cap.latest()
    return status, frame


def cmd_snap(args: argparse.Namespace, cfg: Config) -> int:
    cap = WgcCapture(cfg.window_title)
    try:
        status, frame = _grab_one(cap)
    finally:
        cap.close()
    if frame is None:
        print(f"Kare alınamadı: {status}")
        return 1
    out = Path("samples") / args.label / f"{datetime.now():%Y%m%d-%H%M%S}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), frame)
    print(out)
    return 0


def cmd_record(args: argparse.Namespace, cfg: Config) -> int:
    out_dir = Path("samples") / "replay" / args.label
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = WgcCapture(cfg.window_title)
    saved = 0
    try:
        _grab_one(cap)
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            status, frame = cap.latest()
            if frame is not None:
                saved += 1
                cv2.imwrite(str(out_dir / f"{saved:04d}.png"), frame)
            time.sleep(args.interval)
    finally:
        cap.close()
    print(f"{saved} kare -> {out_dir}")
    return 0 if saved else 1


def cmd_ocr(args: argparse.Namespace, cfg: Config) -> int:
    from ko_monitor.ocr import Ocr

    image = _read_image(args.image)
    ox, oy = 0, 0
    if args.roi:
        ox, oy = args.roi[0], args.roi[1]
        image = crop(image, args.roi)
    for line in Ocr(min_score=0.0).read_block(image):
        x, y, w, h = line.box
        print(f"{line.score:.2f}  x={x + ox} y={y + oy} w={w} h={h}  {line.text}")
    return 0


def cmd_crop(args: argparse.Namespace, cfg: Config) -> int:
    part = crop(_read_image(args.image), args.roi)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.out), part)
    print(f"{args.out} ({part.shape[1]}x{part.shape[0]})")
    return 0


def cmd_detect(args: argparse.Namespace, cfg: Config) -> int:
    from ko_monitor.detectors import Detector
    from ko_monitor.ocr import Ocr

    calib = load_calibration(cfg.calibration_path)
    detector = Detector(calib, Ocr(calib.ocr_min_score))
    for path in args.images:
        readings = detector.detect(_read_image(path))
        payload = None if readings is None else dataclasses.asdict(readings)
        print(path, json.dumps(payload, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ko_monitor")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snap", help="save the current game frame to samples/<label>/")
    snap.add_argument("label")
    snap.set_defaults(func=cmd_snap)

    record = sub.add_parser("record", help="save frames to samples/replay/<label>/ for replay")
    record.add_argument("label")
    record.add_argument("--seconds", type=float, default=30.0)
    record.add_argument("--interval", type=float, default=2.0)
    record.set_defaults(func=cmd_record)

    ocr = sub.add_parser("ocr", help="print all text found in an image (full-frame coordinates)")
    ocr.add_argument("image", type=Path)
    ocr.add_argument("--roi", type=parse_roi)
    ocr.set_defaults(func=cmd_ocr)

    crop_cmd = sub.add_parser("crop", help="cut a region out of an image (for templates)")
    crop_cmd.add_argument("image", type=Path)
    crop_cmd.add_argument("--roi", type=parse_roi, required=True)
    crop_cmd.add_argument("--out", type=Path, required=True)
    crop_cmd.set_defaults(func=cmd_crop)

    detect = sub.add_parser("detect", help="print Readings for images using calibration.json")
    detect.add_argument("images", type=Path, nargs="+")
    detect.set_defaults(func=cmd_detect)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args, load_config(args.config))
```

- [ ] **Step 6: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_templates.py tests/test_inventory.py tests/test_frame_diff.py tests/test_detector.py tests/test_cli.py -q`
Expected: `13 passed` (templates 4 + inventory 4 + frame_diff 1 + detector 2 + cli 2)

- [ ] **Step 7: Komutları gerçek örnekte dene**

Run: `.venv\Scripts\python.exe -m ko_monitor detect samples\normal\spike-desktop.png`
Expected: satırda `"hud_visible": true, "hp": 9718, "hp_max": 9996, "zone": "Ronark Land"` görünür.

- [ ] **Step 8: Tüm testler + commit**

Run: `.venv\Scripts\python.exe -m pytest -q` → Expected: tümü PASS
```powershell
git add src/ko_monitor/detectors src/ko_monitor/cli.py tests/test_templates.py tests/test_inventory.py tests/test_frame_diff.py tests/test_detector.py tests/test_cli.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: template, inventory and frame-diff detectors; detector assembly; calibration commands" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: İzleme durum makinesi (`Monitor`)

**Files:**
- Create: `src/ko_monitor/monitor.py`
- Test: `tests/test_monitor.py`

**Interfaces:**
- Consumes: `Thresholds` (Task 1); `State`, `CaptureStatus`, `EventKind`, `Event`, `Readings`, `Snapshot` (Task 2)
- Produces:
  - `Observation(ts: float, process_running: bool, capture: CaptureStatus | None = None, readings: Readings | None = None)`
  - `Monitor(thresholds: Thresholds)` with `observe(obs: Observation) -> list[Event]`, `snapshot(ts: float) -> Snapshot`, attribute `state: State | None`
  - Olay `detail` değerleri: kötü durum ve `INVENTORY_FULL` için son bilinen bölge adı (yoksa `""`); `RECOVERED` için önceki durumun değeri (`"dead"` vb.); diğerleri `""`.

Kurallar (spec §5): kötü duruma girişte `notify=True`; öncelik Kapalı > Kör > Disconnect > Ölü > Donmuş > Canlı; Kör onaylanana kadar durum korunur; çıkış olumlu okuma ister; envanter dolu 600 sn'de bir.

- [ ] **Step 1: Failing test yaz**

`tests/test_monitor.py`:
```python
import pytest

from ko_monitor.config import Thresholds
from ko_monitor.models import CaptureStatus, EventKind, Readings, State
from ko_monitor.monitor import Monitor, Observation

T = Thresholds()


def readings(**overrides) -> Readings:
    base = dict(hud_visible=True, hp=9000, hp_max=9996, zone="Ronark Land", frame_diff=5.0)
    base.update(overrides)
    return Readings(**base)


def ok(ts: float, **overrides) -> Observation:
    return Observation(ts, True, CaptureStatus.OK, readings(**overrides))


NO_HUD = dict(hud_visible=False, hp=None, hp_max=None, zone=None)


def kinds(events):
    return [(e.kind, e.notify) for e in events]


@pytest.fixture
def m() -> Monitor:
    monitor = Monitor(T)
    monitor.observe(ok(0.0))
    return monitor


def test_closed_at_start_is_silent():
    monitor = Monitor(T)
    assert monitor.observe(Observation(0.0, False)) == []
    assert monitor.state == State.CLOSED


def test_game_start_is_logged_not_notified():
    monitor = Monitor(T)
    assert kinds(monitor.observe(ok(0.0))) == [(EventKind.GAME_STARTED, False)]
    assert monitor.state == State.ALIVE


def test_death_needs_two_reads_and_notifies_once(m):
    assert m.observe(ok(2, hp=0)) == []
    events = m.observe(ok(4, hp=0))
    assert kinds(events) == [(EventKind.DEAD, True)]
    assert events[0].detail == "Ronark Land"
    assert m.observe(ok(6, hp=0)) == []
    assert m.state == State.DEAD


def test_revive_dialog_counts_as_death(m):
    m.observe(ok(2, revive_dialog=True))
    assert kinds(m.observe(ok(4, revive_dialog=True))) == [(EventKind.DEAD, True)]


def test_unreadable_hp_does_not_recover(m):
    m.observe(ok(2, hp=0))
    m.observe(ok(4, hp=0))
    assert m.observe(ok(6, **NO_HUD)) == []
    assert m.state == State.DEAD
    events = m.observe(ok(8, hp=5000))
    assert kinds(events) == [(EventKind.RECOVERED, False)]
    assert events[0].detail == "dead"


def test_explicit_disconnect(m):
    assert m.observe(ok(2, **NO_HUD, login_screen=True)) == []
    assert kinds(m.observe(ok(4, **NO_HUD, login_screen=True))) == [(EventKind.DISCONNECTED, True)]


def test_hud_missing_means_disconnect_after_15s(m):
    assert m.observe(ok(2, **NO_HUD)) == []
    assert m.observe(ok(16, **NO_HUD)) == []
    assert kinds(m.observe(ok(17, **NO_HUD))) == [(EventKind.DISCONNECTED, True)]
    assert kinds(m.observe(ok(19))) == [(EventKind.RECOVERED, False)]


def test_frozen_after_120s_and_recovers_on_change(m):
    assert m.observe(ok(2, frame_diff=0.0)) == []
    assert m.observe(ok(121, frame_diff=0.0)) == []
    assert kinds(m.observe(ok(122, frame_diff=0.0))) == [(EventKind.FROZEN, True)]
    assert kinds(m.observe(ok(124, frame_diff=3.0))) == [(EventKind.RECOVERED, False)]


def test_frozen_not_reported_while_dead(m):
    m.observe(ok(2, hp=0, frame_diff=0.0))
    m.observe(ok(4, hp=0, frame_diff=0.0))
    assert m.observe(ok(200, hp=0, frame_diff=0.0)) == []
    assert m.state == State.DEAD


def test_blind_after_60s_then_recovers(m):
    assert m.observe(Observation(2, True, CaptureStatus.MINIMIZED)) == []
    assert m.observe(Observation(61, True, CaptureStatus.MINIMIZED)) == []
    assert kinds(m.observe(Observation(62, True, CaptureStatus.MINIMIZED))) == [(EventKind.BLIND, True)]
    assert kinds(m.observe(ok(64))) == [(EventKind.RECOVERED, False)]


def test_short_blind_during_death_does_not_renotify(m):
    m.observe(ok(2, hp=0))
    m.observe(ok(4, hp=0))
    assert m.observe(Observation(6, True, CaptureStatus.MINIMIZED)) == []
    assert m.observe(Observation(30, True, CaptureStatus.BLACK)) == []
    assert m.state == State.DEAD
    assert m.observe(ok(32, hp=0)) == []
    assert m.state == State.DEAD


def test_unreadable_frame_counts_as_blind(m):
    assert m.observe(Observation(2, True, CaptureStatus.OK, None)) == []
    assert kinds(m.observe(Observation(62, True, CaptureStatus.OK, None))) == [(EventKind.BLIND, True)]


def test_disconnect_outranks_death(m):
    m.observe(ok(2, hp=0, login_screen=True))
    assert kinds(m.observe(ok(4, hp=0, login_screen=True))) == [(EventKind.DISCONNECTED, True)]


def test_death_then_disconnect_notifies_again(m):
    m.observe(ok(2, hp=0))
    m.observe(ok(4, hp=0))
    assert m.observe(ok(6, **NO_HUD, disconnect_dialog=True)) == []
    assert kinds(m.observe(ok(8, **NO_HUD, disconnect_dialog=True))) == [(EventKind.DISCONNECTED, True)]


def test_game_closed_while_monitoring(m):
    assert kinds(m.observe(Observation(10, False))) == [(EventKind.GAME_CLOSED, True)]
    assert m.observe(Observation(20, False)) == []
    assert kinds(m.observe(ok(30))) == [(EventKind.GAME_STARTED, False)]


def test_inventory_full_from_chat_is_throttled(m):
    assert kinds(m.observe(ok(2, chat_events=["inventory_full"]))) == [(EventKind.INVENTORY_FULL, True)]
    assert m.observe(ok(100, chat_events=["inventory_full"])) == []
    assert kinds(m.observe(ok(602, chat_events=["inventory_full"]))) == [(EventKind.INVENTORY_FULL, True)]


def test_inventory_full_from_slots_and_snapshot_keeps_last_seen(m):
    events = m.observe(ok(2, inventory_open=True, money=1_500_000, slots_used=28, slots_total=28))
    assert kinds(events) == [(EventKind.INVENTORY_FULL, True)]
    m.observe(ok(4))
    snap = m.snapshot(5)
    assert (snap.state, snap.hp, snap.hp_max, snap.zone) == (State.ALIVE, 9000, 9996, "Ronark Land")
    assert (snap.money_last, snap.slots_used_last, snap.slots_total_last) == (1_500_000, 28, 28)
    assert snap.inventory_seen_at == 2


def test_snapshot_when_closed():
    monitor = Monitor(T)
    monitor.observe(Observation(0, False))
    snap = monitor.snapshot(1)
    assert (snap.state, snap.hp) == (State.CLOSED, None)
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_monitor.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.monitor'`

- [ ] **Step 3: `monitor.py` yaz**

`src/ko_monitor/monitor.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from ko_monitor.config import Thresholds
from ko_monitor.models import CaptureStatus, Event, EventKind, Readings, Snapshot, State

_BAD_EVENTS = {
    State.DEAD: EventKind.DEAD,
    State.DISCONNECTED: EventKind.DISCONNECTED,
    State.FROZEN: EventKind.FROZEN,
    State.BLIND: EventKind.BLIND,
}


@dataclass(frozen=True)
class Observation:
    ts: float
    process_running: bool
    capture: CaptureStatus | None = None
    readings: Readings | None = None


class Monitor:
    """Pure state machine: observations in, events out. No I/O, no clock."""

    def __init__(self, thresholds: Thresholds):
        self._t = thresholds
        self.state: State | None = None
        self.zone_last: str | None = None
        self.money_last: int | None = None
        self.slots_used_last: int | None = None
        self.slots_total_last: int | None = None
        self.inventory_seen_at: float | None = None
        self._last_inventory_alert: float | None = None
        self._reset_conditions()

    def _reset_conditions(self) -> None:
        self.last_readings: Readings | None = None
        self._blind_since: float | None = None
        self._hud_missing_since: float | None = None
        self._still_since: float | None = None
        self._dead_reads = 0
        self._disconnect_reads = 0

    def observe(self, obs: Observation) -> list[Event]:
        events: list[Event] = []
        if not obs.process_running:
            if self.state not in (None, State.CLOSED):
                events.append(Event(EventKind.GAME_CLOSED, obs.ts, notify=True))
            self._reset_conditions()
            self.state = State.CLOSED
            return events

        if self.state in (None, State.CLOSED):
            events.append(Event(EventKind.GAME_STARTED, obs.ts))
            self.state = State.ALIVE

        if obs.capture == CaptureStatus.OK and obs.readings is not None:
            self._blind_since = None
            self._update(obs.ts, obs.readings)
            events.extend(self._inventory_events(obs.ts, obs.readings))
        elif self._blind_since is None:
            self._blind_since = obs.ts

        target = self._target_state(obs.ts)
        if target != self.state:
            previous = self.state
            self.state = target
            if target == State.ALIVE:
                events.append(Event(EventKind.RECOVERED, obs.ts, previous.value))
            else:
                events.append(Event(_BAD_EVENTS[target], obs.ts, self.zone_last or "", notify=True))
        return events

    def _update(self, ts: float, r: Readings) -> None:
        self.last_readings = r
        if r.zone:
            self.zone_last = r.zone

        if r.hp == 0 or r.revive_dialog:
            self._dead_reads += 1
        elif r.hp is not None and r.hp > 0:
            self._dead_reads = 0

        if r.login_screen or r.disconnect_dialog:
            self._disconnect_reads += 1
        elif r.hud_visible:
            self._disconnect_reads = 0

        if r.hud_visible:
            self._hud_missing_since = None
        elif self._hud_missing_since is None:
            self._hud_missing_since = ts

        if r.frame_diff is not None:
            if r.frame_diff <= self._t.frozen_diff_max:
                if self._still_since is None:
                    self._still_since = ts
            else:
                self._still_since = None

        if r.inventory_open:
            self.inventory_seen_at = ts
            if r.money is not None:
                self.money_last = r.money
            if r.slots_used is not None:
                self.slots_used_last = r.slots_used
                self.slots_total_last = r.slots_total

    def _inventory_events(self, ts: float, r: Readings) -> list[Event]:
        full_by_slots = bool(r.inventory_open) and r.slots_used is not None and r.slots_used == r.slots_total
        if "inventory_full" not in r.chat_events and not full_by_slots:
            return []
        last = self._last_inventory_alert
        if last is not None and ts - last < self._t.inventory_full_repeat_s:
            return []
        self._last_inventory_alert = ts
        return [Event(EventKind.INVENTORY_FULL, ts, self.zone_last or "", notify=True)]

    def _target_state(self, ts: float) -> State:
        t = self._t
        if self._blind_since is not None:
            return State.BLIND if ts - self._blind_since >= t.blind_s else self.state
        if self._disconnect_reads >= t.confirm_reads:
            return State.DISCONNECTED
        if self._hud_missing_since is not None and ts - self._hud_missing_since >= t.disconnect_soft_s:
            return State.DISCONNECTED
        if self._dead_reads >= t.confirm_reads:
            return State.DEAD
        if (
            self.state in (State.ALIVE, State.FROZEN)
            and self._still_since is not None
            and ts - self._still_since >= t.frozen_s
        ):
            return State.FROZEN
        return State.ALIVE

    def snapshot(self, ts: float) -> Snapshot:
        r = self.last_readings
        return Snapshot(
            ts=ts,
            state=self.state or State.CLOSED,
            hp=r.hp if r else None,
            hp_max=r.hp_max if r else None,
            zone=self.zone_last,
            money_last=self.money_last,
            slots_used_last=self.slots_used_last,
            slots_total_last=self.slots_total_last,
            inventory_seen_at=self.inventory_seen_at,
        )
```

- [ ] **Step 4: Testin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_monitor.py -q`
Expected: `18 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/ko_monitor/monitor.py tests/test_monitor.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: monitor state machine with debounce, priority and throttling" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Bildirim metinleri, VAPID, Web Push notifier ve healthchecks.io heartbeat

**Files:**
- Create: `src/ko_monitor/messages.py`, `src/ko_monitor/vapid.py`, `src/ko_monitor/notifier.py`, `src/ko_monitor/heartbeat.py`
- Test: `tests/test_messages.py`, `tests/test_vapid.py`, `tests/test_notifier.py`, `tests/test_heartbeat.py`

**Interfaces:**
- Consumes: `Event`, `EventKind` (Task 2); `Storage.subscriptions()`, `Storage.delete_subscription()` (Task 2)
- Produces:
  - `render(event: Event) -> dict` → `{"title": str, "body": str, "url": "/#/events", "kind": str, "ts": float}` — **Plan 2'deki service worker bu JSON'u bekler.**
  - `ensure_vapid_key(path: Path) -> Path`, `application_server_key(path: Path) -> str` (base64url, 87 karakter) — Plan 2 `GET /api/push/vapid-key` bunu kullanır
  - `Notifier` Protocol `send(event) -> bool`; `WebPushNotifier(storage, vapid_key_path: Path, contact: str, max_age_s: float = 300.0, send=webpush, sleep=time.sleep, now=time.time)`; `PrintNotifier()`
  - `Heartbeat(ping_url: str, api_key: str, client: httpx.Client | None = None)` with `enabled: bool`, `ping() -> bool`, `pause() -> bool`

- [ ] **Step 1: Failing testleri yaz**

`tests/test_messages.py`:
```python
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
```

`tests/test_vapid.py`:
```python
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
```

`tests/test_notifier.py`:
```python
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
```

`tests/test_heartbeat.py`:
```python
import httpx

from ko_monitor.heartbeat import Heartbeat

URL = "https://hc-ping.com/1234-abcd"


def client_recording(requests, status=200):
    def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(status)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_disabled_without_url():
    requests = []
    hb = Heartbeat("", "key", client_recording(requests))
    assert not hb.enabled
    assert hb.ping() is False and hb.pause() is False
    assert requests == []


def test_ping():
    requests = []
    assert Heartbeat(URL, "", client_recording(requests)).ping() is True
    assert (requests[0].method, str(requests[0].url)) == ("GET", URL)


def test_ping_failure_is_reported_not_raised():
    assert Heartbeat(URL, "", client_recording([], status=500)).ping() is False


def test_pause_uses_management_api():
    requests = []
    assert Heartbeat(URL, "secret", client_recording(requests)).pause() is True
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://healthchecks.io/api/v3/checks/1234-abcd/pause"
    assert request.headers["X-Api-Key"] == "secret"


def test_pause_needs_api_key():
    requests = []
    assert Heartbeat(URL, "", client_recording(requests)).pause() is False
    assert requests == []
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_messages.py tests/test_vapid.py tests/test_notifier.py tests/test_heartbeat.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.messages'`

- [ ] **Step 3: `messages.py` ve `vapid.py` yaz**

`src/ko_monitor/messages.py`:
```python
from __future__ import annotations

from datetime import datetime

from ko_monitor.models import Event, EventKind

TITLES = {
    EventKind.DEAD: "💀 Karakter öldü",
    EventKind.INVENTORY_FULL: "🎒 Envanter dolu",
    EventKind.DISCONNECTED: "🔌 Sunucudan düştün",
    EventKind.GAME_CLOSED: "❌ Oyun kapandı",
    EventKind.FROZEN: "🧊 Oyun ekranı dondu",
    EventKind.BLIND: "🙈 İzleme yapılamıyor",
    EventKind.GAME_STARTED: "▶️ Oyun açıldı",
    EventKind.RECOVERED: "✅ Düzeldi",
}


def render(event: Event) -> dict:
    when = datetime.fromtimestamp(event.ts).strftime("%H:%M")
    return {
        "title": TITLES[event.kind],
        "body": f"{event.detail} · {when}" if event.detail else when,
        "url": "/#/events",
        "kind": event.kind.value,
        "ts": event.ts,
    }
```

`src/ko_monitor/vapid.py`:
```python
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
```

- [ ] **Step 4: `notifier.py` ve `heartbeat.py` yaz**

`src/ko_monitor/notifier.py`:
```python
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pywebpush import WebPushException, webpush

from ko_monitor.messages import render
from ko_monitor.models import Event

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def send(self, event: Event) -> bool: ...


class PrintNotifier:
    """Used by --replay: logs instead of pushing to the phone."""

    def send(self, event: Event) -> bool:
        message = render(event)
        log.info("[bildirim] %s — %s", message["title"], message["body"])
        return False


class WebPushNotifier:
    def __init__(
        self,
        storage,
        vapid_key_path: Path,
        contact: str,
        max_age_s: float = 300.0,
        send: Callable[..., object] = webpush,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
    ):
        self._storage = storage
        self._key_path = vapid_key_path
        self._contact = contact
        self._max_age_s = max_age_s
        self._send = send
        self._sleep = sleep
        self._now = now

    def send(self, event: Event) -> bool:
        if self._now() - event.ts > self._max_age_s:
            log.warning("dropping stale notification %s", event.kind)
            return False
        payload = json.dumps(render(event), ensure_ascii=False)
        delivered = False
        for subscription in self._storage.subscriptions():
            delivered = self._deliver(subscription, payload) or delivered
        return delivered

    def _deliver(self, subscription: dict, payload: str) -> bool:
        for attempt in range(3):
            try:
                self._send(
                    subscription_info=subscription,
                    data=payload,
                    vapid_private_key=str(self._key_path),
                    vapid_claims={"sub": self._contact},
                    ttl=int(self._max_age_s),
                )
                return True
            except WebPushException as exc:
                if getattr(exc, "status_code", None) in (404, 410):
                    log.info("push subscription gone, removing %s", subscription["endpoint"])
                    self._storage.delete_subscription(subscription["endpoint"])
                    return False
                log.warning("push failed (attempt %d): %s", attempt + 1, exc)
            except Exception:
                log.exception("push failed (attempt %d)", attempt + 1)
            if attempt < 2:
                self._sleep(2**attempt)
        return False
```

`src/ko_monitor/heartbeat.py`:
```python
from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


class Heartbeat:
    """healthchecks.io: ping while the game is monitored, pause when it closes normally."""

    def __init__(self, ping_url: str, api_key: str, client: httpx.Client | None = None):
        self._ping_url = ping_url.rstrip("/")
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=10.0)

    @property
    def enabled(self) -> bool:
        return bool(self._ping_url)

    def ping(self) -> bool:
        if not self.enabled:
            return False
        try:
            self._client.get(self._ping_url).raise_for_status()
            return True
        except httpx.HTTPError as exc:
            log.warning("heartbeat ping failed: %s", exc)
            return False

    def pause(self) -> bool:
        if not (self.enabled and self._api_key):
            return False
        check_uuid = self._ping_url.rsplit("/", 1)[-1]
        try:
            self._client.post(
                f"https://healthchecks.io/api/v3/checks/{check_uuid}/pause",
                headers={"X-Api-Key": self._api_key},
            ).raise_for_status()
            return True
        except httpx.HTTPError as exc:
            log.warning("heartbeat pause failed: %s", exc)
            return False
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_messages.py tests/test_vapid.py tests/test_notifier.py tests/test_heartbeat.py -q`
Expected: `15 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/ko_monitor/messages.py src/ko_monitor/vapid.py src/ko_monitor/notifier.py src/ko_monitor/heartbeat.py tests/test_messages.py tests/test_vapid.py tests/test_notifier.py tests/test_heartbeat.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: Turkish push messages, VAPID keys, web push notifier and heartbeat" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Ajan döngüsü, `run` (canlı ve `--replay`) ve `vapid` komutları

**Files:**
- Create: `src/ko_monitor/agent.py`
- Modify: `src/ko_monitor/cli.py` — Task 6 sürümüne `cmd_run`, `cmd_vapid` fonksiyonları ve iki parser eklenir (tam kod aşağıda)
- Test: `tests/test_agent.py`, `tests/test_replay.py`

**Interfaces:**
- Consumes: `Config` (Task 1); `Storage` (Task 2); `FrameSource`, `ReplaySource`, `WgcCapture` (Task 3); `load_calibration` (Task 4); `Ocr` (Task 4); `Detector` (Task 6); `Monitor`, `Observation` (Task 7); `Notifier`, `WebPushNotifier`, `PrintNotifier`, `Heartbeat`, `ensure_vapid_key`, `application_server_key` (Task 8); `is_process_running` (Task 3); `setup_logging` (Task 1)
- Produces:
  - `Agent(cfg, storage, source, detector, monitor, notifier, heartbeat, process_running: Callable[[], bool], now: Callable[[], float] = time.time)` with `tick() -> float` (sonraki bekleme süresi) and `run(stop: threading.Event) -> None`; `Agent.monitor` özelliği (Plan 2 durum API'si okuyacak)
  - `SimClock(start: float, step: float)` with `now()`, `advance()`
  - `run_replay(cfg, folder: Path, detector, storage) -> list[dict]` (olaylar eskiden yeniye)
  - CLI: `run [--replay DIR]`, `vapid`

- [ ] **Step 1: Failing testleri yaz**

`tests/test_agent.py`:
```python
from pathlib import Path

import numpy as np
import pytest

from ko_monitor.agent import Agent
from ko_monitor.config import Config
from ko_monitor.models import CaptureStatus, Readings
from ko_monitor.monitor import Monitor
from ko_monitor.storage import Storage

FRAME = np.zeros((1, 1, 3), np.uint8)


def alive(**overrides):
    base = dict(hud_visible=True, hp=9000, hp_max=9996, zone="Ronark Land", frame_diff=5.0)
    base.update(overrides)
    return Readings(**base)


class FakeSource:
    def latest(self):
        return CaptureStatus.OK, FRAME

    def close(self):
        pass


class FakeDetector:
    def __init__(self):
        self.next = alive()

    def detect(self, frame):
        if isinstance(self.next, Exception):
            raise self.next
        return self.next


class FakeNotifier:
    def __init__(self, result=True):
        self.result = result
        self.sent = []

    def send(self, event):
        self.sent.append(event)
        return self.result


class FakeHeartbeat:
    def __init__(self):
        self.pings = 0
        self.pauses = 0

    def ping(self):
        self.pings += 1
        return True

    def pause(self):
        self.pauses += 1
        return True


class Harness:
    def __init__(self, tmp_path: Path, notify_result=True):
        self.cfg = Config(data_dir=tmp_path)
        self.storage = Storage(tmp_path / "db.sqlite3")
        self.detector = FakeDetector()
        self.notifier = FakeNotifier(notify_result)
        self.heartbeat = FakeHeartbeat()
        self.clock = 0.0
        self.running = True
        self.agent = Agent(
            self.cfg, self.storage, FakeSource(), self.detector, Monitor(self.cfg.thresholds),
            self.notifier, self.heartbeat, lambda: self.running, now=lambda: self.clock,
        )

    def tick_at(self, ts: float, readings=None, running=True) -> float:
        self.clock = ts
        self.running = running
        if readings is not None:
            self.detector.next = readings
        return self.agent.tick()

    def kinds(self):
        return [(e["kind"], e["notified"]) for e in reversed(self.storage.recent_events())]


@pytest.fixture
def h(tmp_path):
    harness = Harness(tmp_path)
    yield harness
    harness.storage.close()


def test_death_is_stored_and_notified(h):
    assert h.tick_at(0, alive()) == 2.0
    h.tick_at(2, alive(hp=0))
    h.tick_at(4, alive(hp=0))
    assert h.kinds() == [("game_started", False), ("dead", True)]
    assert [e.kind.value for e in h.notifier.sent] == ["dead"]


def test_failed_notification_is_not_marked(tmp_path):
    harness = Harness(tmp_path, notify_result=False)
    harness.tick_at(0, alive())
    harness.tick_at(2, alive(hp=0))
    harness.tick_at(4, alive(hp=0))
    assert harness.kinds()[-1] == ("dead", False)
    harness.storage.close()


def test_game_closed_pauses_heartbeat_and_slows_polling(h):
    h.tick_at(0)
    assert h.tick_at(6, running=False) == 10.0
    assert h.heartbeat.pauses == 1
    assert h.kinds()[-1] == ("game_closed", True)


def test_snapshot_and_ping_every_60s_only_while_running(h):
    h.tick_at(0)
    h.tick_at(30)
    h.tick_at(60)
    h.tick_at(200, running=False)
    assert [s.ts for s in h.storage.snapshots_since(0)] == [0, 60]
    assert h.heartbeat.pings == 2


def test_detector_crash_does_not_stop_the_loop(h):
    h.tick_at(0)
    assert h.tick_at(2, RuntimeError("boom")) == 2.0
    assert h.agent.monitor.state.value == "alive"
```

`tests/test_replay.py`:
```python
import pytest

from helpers import SAMPLES
from ko_monitor.agent import run_replay
from ko_monitor.config import Config
from ko_monitor.detectors import Detector
from ko_monitor.storage import Storage


@pytest.mark.ocr
def test_replay_of_normal_frames(tmp_path, calib, ocr):
    storage = Storage(tmp_path / "replay.sqlite3")
    events = run_replay(Config(data_dir=tmp_path), SAMPLES / "normal", Detector(calib, ocr), storage)
    assert [e["kind"] for e in events] == ["game_started", "game_closed"]
    snapshots = storage.snapshots_since(0)
    assert len(snapshots) == 1
    assert (snapshots[0].state.value, snapshots[0].hp, snapshots[0].zone) == ("alive", 9718, "Ronark Land")
    storage.close()
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent.py tests/test_replay.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ko_monitor.agent'`

- [ ] **Step 3: `agent.py` yaz**

`src/ko_monitor/agent.py`:
```python
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from ko_monitor.capture import FrameSource, ReplaySource
from ko_monitor.config import Config
from ko_monitor.heartbeat import Heartbeat
from ko_monitor.models import CaptureStatus, Event, EventKind
from ko_monitor.monitor import Monitor, Observation
from ko_monitor.notifier import Notifier, PrintNotifier
from ko_monitor.storage import Storage

log = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        cfg: Config,
        storage: Storage,
        source: FrameSource,
        detector,
        monitor: Monitor,
        notifier: Notifier,
        heartbeat,
        process_running: Callable[[], bool],
        now: Callable[[], float] = time.time,
    ):
        self._cfg = cfg
        self._storage = storage
        self._source = source
        self._detector = detector
        self.monitor = monitor
        self._notifier = notifier
        self._heartbeat = heartbeat
        self._process_running = process_running
        self._now = now
        self._last_snapshot = float("-inf")

    def tick(self) -> float:
        """One loop iteration. Returns the number of seconds to wait before the next one."""
        ts = self._now()
        running = self._process_running()
        if running:
            status, frame = self._source.latest()
            readings = None
            if status == CaptureStatus.OK and frame is not None:
                try:
                    readings = self._detector.detect(frame)
                except Exception:
                    log.exception("detector failed")
            observation = Observation(ts, True, status, readings)
        else:
            observation = Observation(ts, False)

        for event in self.monitor.observe(observation):
            self._handle(event)

        t = self._cfg.thresholds
        if running and ts - self._last_snapshot >= t.snapshot_s:
            self._last_snapshot = ts
            self._storage.add_snapshot(self.monitor.snapshot(ts))
            self._storage.prune_snapshots(ts - t.snapshot_retention_s)
            self._heartbeat.ping()
        return t.tick_s if running else t.closed_poll_s

    def _handle(self, event: Event) -> None:
        event_id = self._storage.add_event(event)
        log.info("event %s %s", event.kind.value, event.detail)
        if event.kind == EventKind.GAME_CLOSED:
            self._heartbeat.pause()
        if event.notify and self._notifier.send(event):
            self._storage.mark_notified(event_id, self._now())

    def run(self, stop: threading.Event) -> None:
        log.info("agent started")
        while not stop.is_set():
            try:
                delay = self.tick()
            except Exception:
                log.exception("tick failed")
                delay = self._cfg.thresholds.tick_s
            stop.wait(delay)
        log.info("agent stopped")


class SimClock:
    def __init__(self, start: float, step: float):
        self._value = start
        self._step = step

    def now(self) -> float:
        return self._value

    def advance(self) -> None:
        self._value += self._step


def run_replay(cfg: Config, folder: Path, detector, storage: Storage) -> list[dict]:
    """Feeds recorded frames through the real pipeline, one tick_s per frame, then 'closes' the game."""
    source = ReplaySource(folder)
    clock = SimClock(time.time(), cfg.thresholds.tick_s)
    agent = Agent(
        cfg, storage, source, detector, Monitor(cfg.thresholds), PrintNotifier(),
        Heartbeat("", ""), lambda: not source.exhausted, now=clock.now,
    )
    while not source.exhausted:
        agent.tick()
        clock.advance()
    agent.tick()
    return list(reversed(storage.recent_events(limit=10_000)))
```

- [ ] **Step 4: `cli.py`'ye `run` ve `vapid` ekle**

`src/ko_monitor/cli.py` içinde `def build_parser()` satırının hemen **üstüne** ekle:
```python
def cmd_run(args: argparse.Namespace, cfg: Config) -> int:
    import threading

    from ko_monitor.agent import Agent, run_replay
    from ko_monitor.detectors import Detector
    from ko_monitor.heartbeat import Heartbeat
    from ko_monitor.logging_setup import setup_logging
    from ko_monitor.monitor import Monitor
    from ko_monitor.notifier import WebPushNotifier
    from ko_monitor.ocr import Ocr
    from ko_monitor.process_watch import is_process_running
    from ko_monitor.storage import Storage
    from ko_monitor.vapid import ensure_vapid_key

    setup_logging(cfg.log_dir)
    calib = load_calibration(cfg.calibration_path)
    detector = Detector(calib, Ocr(calib.ocr_min_score))

    if args.replay:
        db_path = cfg.data_dir / "replay.sqlite3"
        db_path.unlink(missing_ok=True)
        storage = Storage(db_path)
        try:
            for event in run_replay(cfg, args.replay, detector, storage):
                print(f"{event['kind']:<15} {event['detail']}")
        finally:
            storage.close()
        return 0

    storage = Storage(cfg.data_dir / "ko_monitor.sqlite3")
    notifier = WebPushNotifier(
        storage, ensure_vapid_key(cfg.data_dir / "vapid_private.pem"),
        cfg.push.contact, cfg.push.max_age_s,
    )
    source = WgcCapture(cfg.window_title, calib.black_threshold)
    agent = Agent(
        cfg, storage, source, detector, Monitor(cfg.thresholds), notifier,
        Heartbeat(cfg.heartbeat.ping_url, cfg.heartbeat.api_key),
        lambda: is_process_running(cfg.process_name),
    )
    stop = threading.Event()
    try:
        agent.run(stop)
    except KeyboardInterrupt:
        stop.set()
    finally:
        source.close()
        storage.close()
    return 0


def cmd_vapid(args: argparse.Namespace, cfg: Config) -> int:
    from ko_monitor.vapid import application_server_key, ensure_vapid_key

    print(application_server_key(ensure_vapid_key(cfg.data_dir / "vapid_private.pem")))
    return 0


```

`build_parser()` içinde `return parser` satırının hemen **üstüne** ekle:
```python
    run = sub.add_parser("run", help="run the monitor (live, or --replay a folder of frames)")
    run.add_argument("--replay", type=Path)
    run.set_defaults(func=cmd_run)

    vapid = sub.add_parser("vapid", help="create the VAPID key if needed and print the public key")
    vapid.set_defaults(func=cmd_vapid)
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent.py tests/test_replay.py -q`
Expected: `6 passed`

- [ ] **Step 6: Komutları dene**

Run: `.venv\Scripts\python.exe -m ko_monitor run --replay samples\normal`
Expected (log satırlarının ardından):
```
game_started
game_closed
```

Run: `.venv\Scripts\python.exe -m ko_monitor vapid`
Expected: 87 karakterlik base64url anahtar; `data\vapid_private.pem` oluşur (git'e girmez).

Oyun açıkken canlı deneme: `.venv\Scripts\python.exe -m ko_monitor run` → logda `capture session started` ve `event game_started` görünür; 60 sn sonra `data\ko_monitor.sqlite3` içinde snapshot oluşur. `Ctrl+C` ile durdur.

- [ ] **Step 7: Tüm testler + commit**

Run: `.venv\Scripts\python.exe -m pytest -q` → Expected: tümü PASS
```powershell
git add src/ko_monitor/agent.py src/ko_monitor/cli.py tests/test_agent.py tests/test_replay.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: agent loop with live and replay run commands" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: Gerçek örneklerle kalibrasyon (kullanıcıyla birlikte)

Bu görev oyunda gerçekleşen anları gerektirir; ekran örneklerini **kullanıcı** oyundayken alır, uygulayıcı ölçer ve `calibration.json`'u doldurur. Kod değişikliği yok; veri + testler.

**Files:**
- Create: `samples/death/*.png`, `samples/inventory_full/*.png`, `samples/inventory_open/*.png`, `samples/disconnect/*.png` (+ isteğe bağlı `samples/replay/death-seq/*.png`)
- Create: `templates/revive_dialog.png`, `templates/login_screen.png` ve/veya `templates/disconnect_dialog.png`, `templates/inventory_window.png`, `templates/empty_slot.png`
- Modify: `calibration.json`
- Test: `tests/test_calibrated_samples.py`

**Interfaces:**
- Consumes: CLI `snap`, `record`, `ocr`, `crop`, `detect`, `run --replay` (Task 3, 6, 9); `Detector` (Task 6); `classify`, `normalize` (Task 5); `crop` (Task 4)
- Produces: `calibration.json` şablon anahtarları `revive_dialog`, `login_screen`, `disconnect_dialog`; `inventory` bloğu; `chat_phrases.inventory_full` (Task 4'teki şema)

- [ ] **Step 1: Kalibre edilmiş örnek testlerini yaz** (örnek klasörü boşken pytest bu testleri "empty parameter set" olarak atlar)

`tests/test_calibrated_samples.py`:
```python
import cv2
import pytest

from helpers import sample_frames
from ko_monitor.calibration import crop
from ko_monitor.detectors import Detector
from ko_monitor.detectors.chat import classify, normalize


def detect(path, calib, ocr):
    readings = Detector(calib, ocr).detect(cv2.imread(str(path)))
    assert readings is not None, "frame resolution does not match calibration.json"
    return readings


def ids(path):
    return f"{path.parent.name}/{path.name}"


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("death"), ids=ids)
def test_death_samples(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.hp == 0 or r.revive_dialog is True


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("disconnect"), ids=ids)
def test_disconnect_samples(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.login_screen is True or r.disconnect_dialog is True


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("inventory_open"), ids=ids)
def test_inventory_open_samples(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.inventory_open is True
    assert r.money is not None
    assert r.slots_used is not None and 0 <= r.slots_used <= r.slots_total


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("inventory_full"), ids=ids)
def test_inventory_full_message_samples(path, calib, ocr):
    frame = cv2.imread(str(path))
    lines = [normalize(line.text) for line in ocr.read_block(crop(frame, calib.chat_roi))]
    assert "inventory_full" in classify(lines, calib.chat_phrases)


@pytest.mark.ocr
@pytest.mark.parametrize(
    "path",
    sample_frames("normal") + sample_frames("inventory_open") + sample_frames("inventory_full"),
    ids=ids,
)
def test_alive_samples_have_no_false_alarms(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.hud_visible and r.hp > 0
    assert r.revive_dialog is not True
    assert r.login_screen is not True and r.disconnect_dialog is not True
```

Run: `.venv\Scripts\python.exe -m pytest tests/test_calibrated_samples.py -q`
Expected: yalnızca `normal` örnekleri çalışır ve PASS; diğerleri SKIPPED.

- [ ] **Step 2: Kullanıcıdan örnekleri al** (oyun açık; komutlar proje kökünden)

| An | Komut | Adet |
|---|---|---|
| Karakter ölü, diriltme penceresi açık | `.venv\Scripts\python.exe -m ko_monitor snap death` | 2 (farklı yerlerde) |
| "Envanter dolu" mesajı chat'e düştüğü an | `.venv\Scripts\python.exe -m ko_monitor snap inventory_full` | 1-2 |
| Envanter penceresi açık, para görünür | `.venv\Scripts\python.exe -m ko_monitor snap inventory_open` | 2 (farklı doluluk) |
| Bağlantı koptu penceresi ve/veya giriş/sunucu seçim ekranı | `.venv\Scripts\python.exe -m ko_monitor snap disconnect` | 1-2 |
| Sıradan oyun, farklı bölgeler | `.venv\Scripts\python.exe -m ko_monitor snap normal` | 2 |
| (İsteğe bağlı) ölümü kapsayan akış | `.venv\Scripts\python.exe -m ko_monitor record death-seq --seconds 40` | 1 |

Her dosyayı açıp doğru anı gösterdiğini kontrol et; yanlış olanları sil.

- [ ] **Step 3: Envanter dolu ifadesi**

Run: `.venv\Scripts\python.exe -m ko_monitor ocr samples\inventory_full\<dosya>.png --roi 1980,960,570,410`
Çıktıda envanter dolu mesajının satırını bul. Sayı/isim içermeyen, mesaja özgü bir parçasını küçük harfle `calibration.json` → `"chat_phrases": {"inventory_full": ["<o parça>"]}` içine yaz (birden fazla varyant varsa hepsini listeye ekle).
Run: `.venv\Scripts\python.exe -m pytest tests/test_calibrated_samples.py -q -k inventory_full` → PASS

- [ ] **Step 4: Ölüm**

Run: `.venv\Scripts\python.exe -m ko_monitor detect samples\death\*.png` (PowerShell joker karakteri genişletmezse dosya adlarını tek tek ver)
- Her satırda `"hp": 0` ise HP ile ölüm zaten çalışıyor; yine de diriltme penceresi şablonunu ekle (HP okunamadığı durumlar için).
- Run: `.venv\Scripts\python.exe -m ko_monitor ocr samples\death\<dosya>.png` → diriltme penceresindeki sabit metnin (başlık veya buton) `x y w h` değerlerini oku.
- Şablonu kes (kutuyu her yönden 4 px genişlet):
  `.venv\Scripts\python.exe -m ko_monitor crop samples\death\<dosya>.png --roi <x-4>,<y-4>,<w+8>,<h+8> --out templates\revive_dialog.png`
- `calibration.json` → `"templates"` içine ekle: `"revive_dialog": {"roi": [<x-40>, <y-40>, <w+80>, <h+80>], "file": "templates/revive_dialog.png", "threshold": 0.8}`
Run: `.venv\Scripts\python.exe -m pytest tests/test_calibrated_samples.py -q -k "death or alive"` → PASS

- [ ] **Step 5: Disconnect**

Step 4'teki yöntemin aynısını `samples\disconnect\` örneklerine uygula:
- Bağlantı koptu penceresi için `templates\disconnect_dialog.png` ve `"disconnect_dialog"` girdisi.
- Giriş/sunucu seçim ekranı için ekrana özgü sabit bir öğeden `templates\login_screen.png` ve `"login_screen"` girdisi.
Aynı biçim: `{"roi": [...], "file": "templates/<ad>.png", "threshold": 0.8}`.
Run: `.venv\Scripts\python.exe -m pytest tests/test_calibrated_samples.py -q -k "disconnect or alive"` → PASS

- [ ] **Step 6: Envanter**

- Run: `.venv\Scripts\python.exe -m ko_monitor ocr samples\inventory_open\<dosya>.png` → pencere başlığı metninin ve para metninin kutularını oku.
- Pencere şablonu: başlık kutusundan (4 px pay) `crop ... --out templates\inventory_window.png`.
- `money_roi`: para kutusunu 6 px genişlet, genişliği en uzun para değerine yetecek kadar sağa uzat.
- Slot ızgarası: görüntüyü Paint'te aç (imlecin piksel koordinatı durum çubuğunda görünür) ve ölç: ilk slotun sol-üst köşesi (`slot_origin`), slot boyutu (`slot_size`), yan ve alt komşu slota mesafe (`slot_step`), sütun/satır sayısı (`cols`, `rows`).
- Boş bir slotu kes: `crop ... --roi <boş slot kutusu> --out templates\empty_slot.png`.
- `calibration.json` → `"inventory"` (Task 4 şeması):
```json
"inventory": {
  "window": {"roi": [<başlık x-40>, <başlık y-40>, <w+80>, <h+80>], "file": "templates/inventory_window.png", "threshold": 0.8},
  "money_roi": [<x>, <y>, <w>, <h>],
  "slot_origin": [<x>, <y>],
  "slot_size": [<w>, <h>],
  "slot_step": [<dx>, <dy>],
  "cols": <sütun>,
  "rows": <satır>,
  "empty_slot_file": "templates/empty_slot.png",
  "empty_max_diff": 12
}
```
- Run: `.venv\Scripts\python.exe -m ko_monitor detect samples\inventory_open\<dosya>.png` → `slots_used` değerini görüntüdeki dolu slot sayısıyla karşılaştır. Fazla sayıyorsa `empty_max_diff`'i artır, eksik sayıyorsa azalt.
Run: `.venv\Scripts\python.exe -m pytest tests/test_calibrated_samples.py -q -k "inventory or alive"` → PASS

- [ ] **Step 7: Eşik ayarı kuralları** (bir test başarısızsa)

- Şablon bulunamıyor → `threshold`'u 0.05 adımlarla düşür (en az 0.7); hâlâ bulunamıyorsa şablonu daha küçük ve sabit bir parçadan yeniden kes.
- Yanlış pozitif (`alive` testi) → `threshold`'u yükselt veya `roi`'yi daralt.

- [ ] **Step 8: Uçtan uca doğrulama**

Run: `.venv\Scripts\python.exe -m pytest -q` → Expected: tümü PASS (örneği olmayan kategoriler SKIPPED)
İsteğe bağlı akış kaydı alındıysa:
Run: `.venv\Scripts\python.exe -m ko_monitor run --replay samples\replay\death-seq`
Expected: `game_started` ardından `dead` (dirilme de kayıttaysa sonra `recovered`), en sonda `game_closed`; `dead` bir kez görünür.

- [ ] **Step 9: Commit**

```powershell
git add calibration.json templates samples tests/test_calibrated_samples.py
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: calibrate death, disconnect and inventory detection from real samples" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Plan 1 sonrası

Plan 1 bittiğinde ajan olayları tespit eder, SQLite'a yazar ve healthchecks.io'ya ping atar; Web Push aboneliği PWA'dan geleceği için telefona bildirim **Plan 2** ile başlar. Plan 2 (FastAPI API, PWA, canlı yayın, Tailscale, Görev Zamanlayıcı) bu planın gerçek koduna dayanarak ayrıca yazılacak. Plan 2'nin güveneceği sözleşmeler: `render()` payload'u (Task 8), `application_server_key()` (Task 8), `Storage` metotları (Task 2), `Agent.monitor` (Task 9), `FrameSource.latest()` (Task 3).
