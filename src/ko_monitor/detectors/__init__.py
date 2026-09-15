"""Frame → Readings detectors."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import numpy as np

from ko_monitor.calibration import Calibration
from ko_monitor.detectors.chat import ChatTracker, read_chat
from ko_monitor.detectors.frame_diff import FrameDiff
from ko_monitor.detectors.hud import read_hud
from ko_monitor.detectors.inventory import read_inventory
from ko_monitor.detectors.templates import template_present
from ko_monitor.models import Readings
from ko_monitor.ocr import Ocr

log = logging.getLogger(__name__)


class Detector:
    """Stateful (chat history, previous frame): use one instance per frame stream."""

    def __init__(
        self,
        calib: Calibration,
        ocr: Ocr,
        chat_interval_s: float = 4.0,
        now: Callable[[], float] = time.monotonic,
    ):
        self._calib = calib
        self._ocr = ocr
        self._chat = ChatTracker()
        self._diff = FrameDiff()
        self._chat_interval_s = chat_interval_s
        self._now = now
        self._last_chat_read: float | None = None
        self._mismatched_size: tuple[int, int] | None = None

    def _chat_events(self, frame: np.ndarray, hud_visible: bool) -> list[str]:
        """Chat OCR (det + rec) is the expensive part of a tick: run it only every chat_interval_s."""
        if not hud_visible:
            return []
        now = self._now()
        if self._last_chat_read is not None and now - self._last_chat_read < self._chat_interval_s:
            return []
        self._last_chat_read = now
        return read_chat(frame, self._calib, self._ocr, self._chat)

    def detect(self, frame: np.ndarray) -> Readings | None:
        height, width = frame.shape[:2]
        if (width, height) != self._calib.resolution:
            if self._mismatched_size != (width, height):
                self._mismatched_size = (width, height)
                expected_w, expected_h = self._calib.resolution
                log.warning(
                    "frame is %dx%d but calibration expects %dx%d; frames are unreadable",
                    width, height, expected_w, expected_h,
                )
            return None
        self._mismatched_size = None
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
            chat_events=self._chat_events(frame, hud_visible),
            inventory_open=inventory_open,
            money=money,
            slots_used=slots_used,
            slots_total=slots_total,
            frame_diff=self._diff.update(frame),
        )
