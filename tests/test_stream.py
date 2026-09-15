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
