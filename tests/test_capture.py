import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.capture import ReplaySource, WgcCapture, is_black
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


class FakeControl:
    """Stand-in for windows_capture's control object."""

    def __init__(self, finished: bool = False):
        self._finished = finished

    def is_finished(self) -> bool:
        return self._finished

    def stop(self) -> None:
        self._finished = True


class FakeClock:
    """A controllable stand-in for time.monotonic."""

    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def test_wgc_window_not_found_returns_status_without_starting(monkeypatch):
    monkeypatch.setattr("ko_monitor.capture.find_window", lambda title: 0)
    cap = WgcCapture("Knight Evolution")
    starts = []
    monkeypatch.setattr(cap, "_start", lambda: starts.append(1))

    status, frame = cap.latest()

    assert (status, frame) == (CaptureStatus.NOT_FOUND, None)
    assert starts == []


def test_wgc_minimized_returns_status_without_starting(monkeypatch):
    monkeypatch.setattr("ko_monitor.capture.find_window", lambda title: 1234)
    monkeypatch.setattr("ko_monitor.capture.is_minimized", lambda hwnd: True)
    cap = WgcCapture("Knight Evolution")
    starts = []
    monkeypatch.setattr(cap, "_start", lambda: starts.append(1))

    status, frame = cap.latest()

    assert (status, frame) == (CaptureStatus.MINIMIZED, None)
    assert starts == []


def test_wgc_backoff_grows_when_session_dies_immediately(monkeypatch):
    monkeypatch.setattr("ko_monitor.capture.find_window", lambda title: 1234)
    monkeypatch.setattr("ko_monitor.capture.is_minimized", lambda hwnd: False)
    clock = FakeClock(0.0)
    monkeypatch.setattr("ko_monitor.capture.time.monotonic", clock)

    cap = WgcCapture("Knight Evolution")
    starts: list[float] = []

    def fake_start():
        starts.append(clock.t)
        cap._control = FakeControl(finished=True)  # session dies right away, no frame

    monkeypatch.setattr(cap, "_start", fake_start)

    clock.t = 0.0
    assert cap.latest() == (CaptureStatus.NOT_FOUND, None)
    assert starts == [0.0]

    clock.t = 0.5
    cap.latest()
    assert starts == [0.0]  # still waiting out the 1s backoff

    clock.t = 1.0
    cap.latest()
    assert starts == [0.0, 1.0]  # first retry after 1s

    clock.t = 2.5
    cap.latest()
    assert starts == [0.0, 1.0]  # still waiting out the 2s backoff

    clock.t = 3.0
    cap.latest()
    assert starts == [0.0, 1.0, 3.0]  # second retry after 2s more


def test_wgc_backoff_grows_when_start_raises(monkeypatch):
    monkeypatch.setattr("ko_monitor.capture.find_window", lambda title: 1234)
    monkeypatch.setattr("ko_monitor.capture.is_minimized", lambda hwnd: False)
    clock = FakeClock(0.0)
    monkeypatch.setattr("ko_monitor.capture.time.monotonic", clock)

    cap = WgcCapture("Knight Evolution")
    starts: list[float] = []

    def fake_start():
        starts.append(clock.t)
        raise RuntimeError("capture session could not start")

    monkeypatch.setattr(cap, "_start", fake_start)

    clock.t = 0.0
    assert cap.latest() == (CaptureStatus.NOT_FOUND, None)
    assert starts == [0.0]
    assert cap._control is None

    clock.t = 0.5
    cap.latest()
    assert starts == [0.0]

    clock.t = 1.0
    cap.latest()
    assert starts == [0.0, 1.0]

    clock.t = 2.5
    cap.latest()
    assert starts == [0.0, 1.0]

    clock.t = 3.0
    cap.latest()
    assert starts == [0.0, 1.0, 3.0]


def test_wgc_backoff_resets_after_a_frame_then_grows_again(monkeypatch):
    monkeypatch.setattr("ko_monitor.capture.find_window", lambda title: 1234)
    monkeypatch.setattr("ko_monitor.capture.is_minimized", lambda hwnd: False)
    clock = FakeClock(0.0)
    monkeypatch.setattr("ko_monitor.capture.time.monotonic", clock)

    cap = WgcCapture("Knight Evolution")
    starts: list[float] = []
    frame = np.full((4, 4, 3), 200, np.uint8)

    def fake_start():
        starts.append(clock.t)
        cap._control = FakeControl(finished=False)
        with cap._lock:
            cap._frame = frame

    monkeypatch.setattr(cap, "_start", fake_start)

    clock.t = 0.0
    status, got = cap.latest()
    assert status == CaptureStatus.OK
    assert got is not None and got[0, 0, 0] == 200
    assert starts == [0.0]
    assert cap._backoff == 1.0  # reset once a frame arrives

    # The session dies; because backoff was reset, the next retry is 1s out,
    # not the larger value it would have grown to without the reset.
    cap._control.stop()

    clock.t = 0.5
    assert cap.latest() == (CaptureStatus.NOT_FOUND, None)
    assert starts == [0.0]  # still within the 1s wait

    clock.t = 1.0
    cap.latest()
    assert starts == [0.0, 1.0]  # retried after exactly 1s


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
