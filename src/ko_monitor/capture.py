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
            # Reserve the next retry slot before attempting, so a session that
            # dies right after starting (protected content, driver error, ...)
            # still backs off instead of retrying every call.
            self._retry_at = now + self._backoff
            self._backoff = min(self._backoff * 2, 30.0)
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
        if self._control is not None and not self._control.is_finished():
            self._control.stop()
        self._control = None
