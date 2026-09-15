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
