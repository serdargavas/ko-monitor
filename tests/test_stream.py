import contextlib
import json
import sys
import threading
import time
from concurrent.futures import CancelledError

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse
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
        # A fresh array each call, like a real capture event producing a new buffer, so tests
        # that expect every tick to be sent aren't tripped up by stream.py's identity dedup.
        frame = None if self.frame is None else self.frame.copy()
        return self.status, frame

    def set_stream_fps(self, fps):
        self.rates.append(fps)

    def close(self):
        pass


class SequenceSource:
    """Returns each frame in order, then repeats the last one — for identity-based tests."""

    def __init__(self, frames):
        self._frames = frames
        self.calls = 0

    def latest(self):
        frame = self._frames[min(self.calls, len(self._frames) - 1)]
        self.calls += 1
        return CaptureStatus.OK, frame

    def set_stream_fps(self, fps):
        pass

    def close(self):
        pass


class ScriptedSource:
    """Returns each (status, frame) pair in order, then repeats the last one."""

    def __init__(self, results):
        self._results = results
        self.calls = 0

    def latest(self):
        result = self._results[min(self.calls, len(self._results) - 1)]
        self.calls += 1
        return result

    def set_stream_fps(self, fps):
        pass

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
            stream_quality=default_quality, web_dir=tmp_path, extra_hosts=["testserver"],
        )
        return TestClient(app)

    yield factory
    for storage in storages:
        storage.close()


def decode(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    assert image is not None, "not a JPEG"
    return image


@contextlib.contextmanager
def open_stream(client: TestClient, url: str, headers: dict | None = None):
    """client.websocket_connect(), tolerant of a test-harness-only cleanup race.

    Starlette's WebSocketTestSession.__exit__ blocks on a future for its background portal
    task; under load (many websocket sessions across test files) that future can occasionally
    surface a bare concurrent.futures.CancelledError from the *portal's own* teardown, well
    after our session's body already ran to completion. It is not raised by our app and
    carries no information about the session itself, so it is swallowed here — a real failure
    inside the `with` block (an assertion, a WebSocketDisconnect from pytest.raises, ...) is
    still propagated untouched.
    """
    session = client.websocket_connect(url, headers=dict(headers or {}))
    ws = session.__enter__()
    try:
        yield ws
    except BaseException:
        with contextlib.suppress(CancelledError):
            session.__exit__(*sys.exc_info())
        raise
    else:
        with contextlib.suppress(CancelledError):
            session.__exit__(None, None, None)


def wait_until(predicate, timeout: float = 2.0, interval: float = 0.02) -> bool:
    """Polls predicate() for an observable condition instead of assuming a fixed delay is enough.

    Needed because a TestClient websocket's `with` block does not guarantee that the server
    handler's cleanup (recording the idle rate, etc.) has already run by the time it returns:
    exiting can race a second cancellation of the handler against its own disconnect cleanup.
    """
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return predicate()
        time.sleep(interval)


def wait_until_stable(get_value, stable_window: float = 0.15, timeout: float = 2.0, interval: float = 0.02):
    """Polls get_value() until it stops changing for stable_window seconds, or times out.

    Used for a negative assertion ("nothing more happens"): rather than guessing a fixed delay
    is long enough, it waits out any in-flight activity and only settles once things go quiet.
    """
    deadline = time.monotonic() + timeout
    value = get_value()
    stable_since = time.monotonic()
    while time.monotonic() - stable_since < stable_window:
        if time.monotonic() >= deadline:
            break
        time.sleep(interval)
        current = get_value()
        if current != value:
            value = current
            stable_since = time.monotonic()
    return value


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
        with open_stream(client, "/api/stream") as ws:
            assert decode(ws.receive_bytes()).shape == (540, 960, 3)
    assert wait_until(lambda: source.rates == [5.0, None])


@pytest.mark.parametrize(
    "quality, shape, fps",
    [("low", (540, 960, 3), 5.0), ("medium", (720, 1280, 3), 10.0), ("high", (1080, 1920, 3), 20.0)],
)
def test_quality_selects_size_and_rate(make_client, quality, shape, fps):
    source = FakeSource()
    with make_client(source) as client:
        with open_stream(client, f"/api/stream?quality={quality}") as ws:
            assert decode(ws.receive_bytes()).shape == shape
            assert decode(ws.receive_bytes()).shape == shape
    assert wait_until(lambda: source.rates == [fps, None])


def test_missing_frame_sends_the_capture_status(make_client):
    with make_client(FakeSource(CaptureStatus.MINIMIZED, None)) as client:
        with open_stream(client, "/api/stream") as ws:
            assert ws.receive_json() == {"status": "minimized"}


def test_capture_error_is_reported_as_not_found(make_client):
    with make_client(FakeSource(error=OSError("session died"))) as client:
        with open_stream(client, "/api/stream") as ws:
            assert ws.receive_json() == {"status": "not_found"}


def test_unknown_quality_is_rejected_without_capturing(make_client):
    source = FakeSource()
    with make_client(source) as client:
        with pytest.raises(WebSocketDisconnect) as info:
            with open_stream(client, "/api/stream?quality=ultra") as ws:
                ws.receive_bytes()
    assert info.value.code == 1008
    assert info.value.reason == "unknown stream quality"
    assert source.calls == 0 and source.rates == []


def test_foreign_origin_is_rejected_without_capturing(make_client):
    # WebSockets are not covered by CORS: any page the browser opens could otherwise watch.
    source = FakeSource()
    with make_client(source) as client:
        with pytest.raises(WebSocketDisconnect) as info:
            with open_stream(client, "/api/stream", headers={"origin": "https://evil.example"}) as ws:
                ws.receive_bytes()
    assert (info.value.code, info.value.reason) == (1008, "origin not allowed")
    assert source.calls == 0 and source.rates == []


def test_foreign_host_cannot_open_the_stream(make_client):
    source = FakeSource()
    with make_client(source) as client:
        with pytest.raises(WebSocketDenialResponse) as info:
            with open_stream(client, "/api/stream", headers={"host": "evil.example", "origin": "http://evil.example"}):
                pass
    assert info.value.status_code == 400
    assert source.calls == 0 and source.rates == []


@pytest.mark.parametrize("headers", [{"origin": "http://testserver"}, {}])
def test_same_host_origin_or_no_origin_streams(make_client, headers):
    with make_client(FakeSource()) as client:
        with open_stream(client, "/api/stream?quality=low", headers=headers) as ws:
            assert decode(ws.receive_bytes()).shape == (540, 960, 3)


def test_stream_stops_capturing_after_the_client_disconnects(make_client):
    source = FakeSource()
    with make_client(source) as client:
        with open_stream(client, "/api/stream?quality=high") as ws:
            ws.receive_bytes()
            ws.receive_bytes()
        # Positive handshake first: wait for the handler's cleanup to actually have run
        # (it records the return to the idle rate) before checking capturing has stopped,
        # instead of guessing a fixed delay is long enough.
        assert wait_until(lambda: source.rates == [20.0, None])
        # A still-running sender would keep incrementing this at 20 fps; wait it out rather
        # than sleeping a fixed amount, so the check is only as long as it needs to be.
        calls = wait_until_stable(lambda: source.calls)
    assert source.calls == calls


def test_fastest_viewer_sets_the_capture_rate(make_client):
    source = FakeSource()
    with make_client(source) as client:
        with open_stream(client, "/api/stream?quality=low") as slow:
            slow.receive_bytes()
            assert wait_until(lambda: source.rates == [5.0])
            with open_stream(client, "/api/stream?quality=high") as fast:
                fast.receive_bytes()
                assert wait_until(lambda: source.rates == [5.0, 20.0])
            assert wait_until(lambda: source.rates == [5.0, 20.0, 5.0])
            slow.receive_bytes()
    assert wait_until(lambda: source.rates == [5.0, 20.0, 5.0, None])


def message_kind(message) -> str:
    if message.get("bytes") is not None:
        return "frame"
    return json.loads(message["text"])["status"]


def test_repeated_status_is_sent_once_until_it_changes(make_client):
    minimized = (CaptureStatus.MINIMIZED, None)
    not_found = (CaptureStatus.NOT_FOUND, None)
    frame_b = np.full((1440, 2560, 3), 200, np.uint8)
    source = ScriptedSource(
        [minimized] * 3 + [(CaptureStatus.OK, FULL_FRAME)] + [minimized] * 3 + [not_found] * 3
        + [(CaptureStatus.OK, frame_b)]
    )
    with make_client(source) as client:
        with open_stream(client, "/api/stream?quality=high") as ws:
            kinds = [message_kind(ws.receive()) for _ in range(5)]
    # A frame in between counts as a change: the same status is sent again after it.
    assert kinds == ["minimized", "frame", "minimized", "not_found", "frame"]


def test_unchanged_frame_is_sent_only_once(make_client):
    frame_a = FULL_FRAME
    frame_b = np.full((1440, 2560, 3), 200, np.uint8)
    # Index 0 and 1 are the very same array object (frame_a repeated); index 2+ all reuse
    # the same frame_b object too, so only the two genuine changes should ever be sent.
    source = SequenceSource([frame_a, frame_a, frame_b, frame_b])
    with make_client(source) as client:
        with open_stream(client, "/api/stream?quality=low") as ws:
            first = decode(ws.receive_bytes())
            second = decode(ws.receive_bytes())
    # JPEG is lossy, so compare with a tolerance — 90 vs. 200 is unmistakable either way.
    assert abs(int(first[0, 0, 0]) - int(frame_a[0, 0, 0])) <= 5
    assert abs(int(second[0, 0, 0]) - int(frame_b[0, 0, 0])) <= 5
