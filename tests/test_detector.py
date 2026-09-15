import cv2
import numpy as np
import pytest

from helpers import SAMPLES
from ko_monitor.detectors import Detector


@pytest.mark.ocr
def test_detect_real_frame(calib, ocr):
    detector = Detector(calib, ocr)
    frame = cv2.imread(str(SAMPLES / "normal" / "spike-desktop.png"))
    r = detector.detect(frame)
    assert (r.hud_visible, r.hp, r.hp_max, r.zone) == (True, 9718, 9996, "Ronark Land")
    assert (r.revive_dialog, r.login_screen, r.disconnect_dialog) == (None, None, None)
    assert (r.inventory_open, r.money, r.slots_used, r.slots_total) == (None, None, None, None)
    assert r.chat_events == []
    assert r.frame_diff is None
    assert detector.detect(frame).frame_diff == 0.0


@pytest.mark.ocr
def test_wrong_resolution_is_unreadable(calib, ocr):
    assert Detector(calib, ocr).detect(np.zeros((1080, 1920, 3), np.uint8)) is None


def test_resolution_mismatch_is_logged_once_per_size(calib, caplog):
    detector = Detector(calib, None)
    small = np.zeros((1080, 1920, 3), np.uint8)
    other = np.zeros((720, 1280, 3), np.uint8)
    with caplog.at_level("WARNING", logger="ko_monitor.detectors"):
        assert detector.detect(small) is None
        assert detector.detect(small) is None
        assert detector.detect(other) is None
    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == 2
    assert "1920x1080" in messages[0] and "1280x720" in messages[1]


def test_chat_is_read_at_most_once_per_chat_interval(calib, monkeypatch):
    import ko_monitor.detectors as detectors

    hud = {"visible": True}
    chat_reads = []
    monkeypatch.setattr(
        detectors, "read_hud", lambda frame, calib, ocr: (hud["visible"], 9000, 9996, "Ronark Land")
    )
    monkeypatch.setattr(detectors, "read_inventory", lambda frame, inv, ocr: (None, None, None, None))
    monkeypatch.setattr(detectors, "template_present", lambda frame, template: None)
    monkeypatch.setattr(
        detectors, "read_chat", lambda frame, calib, ocr, tracker: chat_reads.append(1) or ["inventory_full"]
    )
    clock = {"now": 100.0}
    detector = Detector(calib, None, chat_interval_s=4.0, now=lambda: clock["now"])
    width, height = calib.resolution
    frame = np.zeros((height, width, 3), np.uint8)

    assert detector.detect(frame).chat_events == ["inventory_full"]
    clock["now"] = 103.9
    assert detector.detect(frame).chat_events == []
    clock["now"] = 104.0
    assert detector.detect(frame).chat_events == ["inventory_full"]
    assert len(chat_reads) == 2

    hud["visible"] = False
    clock["now"] = 110.0
    assert detector.detect(frame).chat_events == []
    assert len(chat_reads) == 2
