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
from ko_monitor.origin import origin_allowed

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


def _grab(source: FrameSource) -> tuple[CaptureStatus, np.ndarray | None]:
    """Runs in a worker thread: capture stays off the event loop."""
    try:
        return source.latest()
    except Exception:
        log.exception("stream capture failed")
        return CaptureStatus.NOT_FOUND, None


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
    last_sent: np.ndarray | None = None
    last_status: str | None = None  # status of the previous message; None after a frame
    while True:
        started = loop.time()
        status, frame = await run_in_threadpool(_grab, source)
        if frame is None:
            last_sent = None  # the next real frame is always sent
            if status.value != last_status:
                last_status = status.value
                await websocket.send_json({"status": status.value})
        elif frame is not last_sent:
            payload = await run_in_threadpool(encode_frame, frame, preset)
            last_sent = frame
            last_status = None
            await websocket.send_bytes(payload)
        # else: the same array as last time (source hasn't produced a new one yet) — skip the
        # resize/encode/send work entirely, but still pace the loop normally below.
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
        # Accept first: closing before accept makes uvicorn reject the handshake with HTTP
        # 403, and browsers then see a bare 1006 (indistinguishable from a dropped network
        # connection) instead of the real 1008 reason.
        await websocket.accept()
        if not origin_allowed(websocket.headers):
            # WebSockets bypass CORS: without this any page the browser opens could watch.
            await websocket.close(code=1008, reason="origin not allowed")
            return
        preset = STREAM_PRESETS.get(quality or default_quality)
        if preset is None:
            await websocket.close(code=1008, reason="unknown stream quality")
            return
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
            # Synchronous and first: even if this task is cancelled again while awaiting the
            # gather below (e.g. a second cancellation during server shutdown), the capture
            # rate has already been returned to idle and is never left stuck at a viewer's rate.
            demand.remove(preset.fps)
            for task in (sender, receiver):
                task.cancel()
            # Waits for an in-flight capture to finish, so nothing is captured after this handler ends.
            await asyncio.gather(sender, receiver, return_exceptions=True)
            log.info("live viewer disconnected")

    return router
