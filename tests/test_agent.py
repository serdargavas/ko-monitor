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


class FlakySource(FakeSource):
    def __init__(self):
        self.fail = False

    def latest(self):
        if self.fail:
            raise OSError("capture session died")
        return super().latest()


class Harness:
    def __init__(self, tmp_path: Path, notify_result=True, source=None):
        self.cfg = Config(data_dir=tmp_path)
        self.storage = Storage(tmp_path / "db.sqlite3")
        self.detector = FakeDetector()
        self.notifier = FakeNotifier(notify_result)
        self.heartbeat = FakeHeartbeat()
        self.clock = 0.0
        self.running = True
        self.agent = Agent(
            self.cfg, self.storage, source or FakeSource(), self.detector, Monitor(self.cfg.thresholds),
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


def test_capture_exception_is_observed_as_not_found(tmp_path):
    source = FlakySource()
    harness = Harness(tmp_path, source=source)
    harness.tick_at(0, alive())
    source.fail = True
    assert harness.tick_at(2) == 2.0
    harness.tick_at(61)
    assert harness.kinds()[-1] == ("game_started", False)
    harness.tick_at(62)
    assert harness.kinds()[-1] == ("blind", True)
    harness.storage.close()


class FakeStop:
    def __init__(self, rounds):
        self.rounds = rounds
        self.waits = []

    def is_set(self):
        return len(self.waits) >= self.rounds

    def wait(self, delay):
        self.waits.append(delay)


def test_run_waits_only_for_the_rest_of_the_tick(tmp_path):
    clock = {"mono": 0.0}
    durations = iter([0.5, 3.0, 1.25])

    def work(delay):
        clock["mono"] += next(durations)
        if delay is None:
            raise RuntimeError("tick boom")
        return delay

    delays = iter([2.0, 2.0, None])
    agent = Agent(
        Config(data_dir=tmp_path), None, FakeSource(), FakeDetector(), Monitor(Config().thresholds),
        FakeNotifier(), FakeHeartbeat(), lambda: True, monotonic=lambda: clock["mono"],
    )
    agent.tick = lambda: work(next(delays))
    stop = FakeStop(rounds=3)
    agent.run(stop)
    assert stop.waits == [1.5, 0.0, 0.75]
