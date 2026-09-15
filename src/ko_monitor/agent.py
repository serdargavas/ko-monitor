from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from ko_monitor.capture import FrameSource, ReplaySource
from ko_monitor.config import Config
from ko_monitor.heartbeat import Heartbeat
from ko_monitor.models import CaptureStatus, Event, EventKind
from ko_monitor.monitor import Monitor, Observation
from ko_monitor.notifier import Notifier, PrintNotifier
from ko_monitor.storage import Storage

log = logging.getLogger(__name__)

_INCIDENT_KINDS = {EventKind.DISCONNECTED, EventKind.DEAD, EventKind.FROZEN, EventKind.BLIND}


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
        monotonic: Callable[[], float] = time.monotonic,
        incident_dir: Path | None = None,
        incident_limit: int = 50,
    ):
        self._cfg = cfg
        self._incident_dir = incident_dir if incident_dir is not None else cfg.data_dir / "incidents"
        self._incident_limit = incident_limit
        self._storage = storage
        self._source = source
        self._detector = detector
        self.monitor = monitor
        self._notifier = notifier
        self._heartbeat = heartbeat
        self._process_running = process_running
        self._now = now
        self._monotonic = monotonic
        self._last_snapshot = float("-inf")

    def tick(self) -> float:
        """One loop iteration. Returns the number of seconds to wait before the next one."""
        ts = self._now()
        running = self._process_running()
        frame = None
        if running:
            try:
                status, frame = self._source.latest()
            except Exception:
                log.exception("capture failed")
                status, frame = CaptureStatus.NOT_FOUND, None
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
            if event.kind in _INCIDENT_KINDS and frame is not None:
                self._save_incident(event, frame)

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

    def _save_incident(self, event: Event, frame: np.ndarray) -> None:
        """Keeps the analyzed frame as evidence for tuning detectors; never breaks the tick."""
        try:
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(event.ts))
            path = self._incident_dir / f"{stamp}-{event.kind.value}.png"
            ok, png = cv2.imencode(".png", frame)
            if not ok:
                raise ValueError("PNG encoding failed")
            self._incident_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png.tobytes())
            # Names start with the timestamp, so name order is age order.
            files = sorted(self._incident_dir.glob("*.png"), key=lambda p: p.name)
            for old in files[: max(0, len(files) - self._incident_limit)]:
                old.unlink()
            log.info("incident frame saved: %s", path)
        except Exception:
            log.exception("could not save incident frame to %s", self._incident_dir)

    def run(self, stop: threading.Event) -> None:
        log.info("agent started")
        while not stop.is_set():
            started = self._monotonic()
            try:
                delay = self.tick()
            except Exception:
                log.exception("tick failed")
                delay = self._cfg.thresholds.tick_s
            # Fixed rate: the tick's own work counts toward the delay.
            stop.wait(max(0.0, delay - (self._monotonic() - started)))
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
        # Keep replay evidence apart so its retention never deletes real incident frames.
        incident_dir=cfg.data_dir / "replay_incidents",
    )
    while not source.exhausted:
        agent.tick()
        clock.advance()
    agent.tick()
    return list(reversed(storage.recent_events(limit=10_000)))
