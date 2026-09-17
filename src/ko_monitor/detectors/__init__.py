"""Frame → Readings detectors."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import numpy as np

from ko_monitor.calibration import Calibration
from ko_monitor.detectors.chat import ChatTracker, read_chat
from ko_monitor.detectors.dialog import DialogCache, read_dialog
from ko_monitor.detectors.frame_diff import FrameDiff
from ko_monitor.detectors.genie import read_genie
from ko_monitor.detectors.hud import read_hud
from ko_monitor.detectors.inventory import read_inventory
from ko_monitor.detectors.items import read_items
from ko_monitor.detectors.templates import template_present
from ko_monitor.models import Readings
from ko_monitor.ocr import Ocr

log = logging.getLogger(__name__)

_DIALOG_LOG_MAX = 120


def _either(a: bool | None, b: bool | None) -> bool | None:
    """True if either source saw it; None only when both could not tell."""
    if a or b:
        return True
    if a is None and b is None:
        return None
    return False


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
        self._dialog_text_last: str | None = None
        self._dialog_cache = DialogCache()

    def _log_dialog_text(self, text: str | None) -> None:
        """Logs every change of the center dialog text: the first real disconnect text teaches us."""
        if text == self._dialog_text_last:
            return
        self._dialog_text_last = text
        log.info("dialog text: %r", None if text is None else text[:_DIALOG_LOG_MAX])

    def _chat_events(self, frame: np.ndarray, hud_visible: bool) -> list[str]:
        """Chat OCR (det + rec) is the expensive part of a tick: run it only every chat_interval_s."""
        if not hud_visible:
            return []
        # Detection + recognition over the chat area costs ~1.2 s of CPU, about a third of a core
        # at this interval. With no phrases configured it can only ever return nothing, so it is
        # skipped entirely until the first real "inventory full" line teaches us what to look for.
        if not any(self._calib.chat_phrases.values()):
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
        items = read_items(
            frame, inventory_open, self._calib.inventory, self._calib.items, self._ocr
        )
        # One template match per tick; the rec-only OCR of the text lines runs only while the
        # dialog frame is present, and is skipped while the text pixels are unchanged.
        dialog_text, dialog_revive, dialog_disconnect = read_dialog(
            frame, self._calib.dialog, self._ocr, self._dialog_cache
        )
        self._log_dialog_text(dialog_text)
        return Readings(
            hud_visible=hud_visible,
            hp=hp,
            hp_max=hp_max,
            zone=zone,
            revive_dialog=_either(template_present(frame, templates.get("revive_dialog")), dialog_revive),
            login_screen=template_present(frame, templates.get("login_screen")),
            disconnect_dialog=_either(
                template_present(frame, templates.get("disconnect_dialog")), dialog_disconnect
            ),
            dialog_text=dialog_text,
            chat_events=self._chat_events(frame, hud_visible),
            inventory_open=inventory_open,
            money=money,
            slots_used=slots_used,
            slots_total=slots_total,
            arrow_count=items.arrows,
            arrow_unlimited=items.arrow_unlimited,
            mana_count=items.mana,
            scroll_count=items.scrolls,
            genie_active=read_genie(frame, self._calib.genie),
            frame_diff=self._diff.update(frame),
        )
