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
