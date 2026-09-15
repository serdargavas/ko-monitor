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
