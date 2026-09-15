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
    # dialog is calibrated repo-wide: no dialog on this frame means False, not unknown.
    assert (r.revive_dialog, r.login_screen, r.disconnect_dialog) == (False, None, False)
    assert r.dialog_text is None
    # inventory is calibrated repo-wide; this frame just doesn't have the window open.
    assert (r.inventory_open, r.money, r.slots_used, r.slots_total) == (False, None, None, None)
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


def test_dialog_text_changes_are_logged_once(calib, monkeypatch, caplog):
    import ko_monitor.detectors as detectors

    long_text = "Disconnected " + "x" * 200
    texts = iter([None, "Notice", "Notice", long_text, None, None])
    monkeypatch.setattr(detectors, "read_hud", lambda frame, calib, ocr: (True, 9000, 9996, "Ronark Land"))
    monkeypatch.setattr(detectors, "read_inventory", lambda frame, inv, ocr: (None, None, None, None))
    monkeypatch.setattr(detectors, "read_chat", lambda frame, calib, ocr, tracker: [])
    monkeypatch.setattr(detectors, "template_present", lambda frame, spec: None)
    monkeypatch.setattr(detectors, "read_dialog", lambda frame, spec, ocr, *args: (next(texts), False, False))
    width, height = calib.resolution
    frame = np.zeros((height, width, 3), np.uint8)
    detector = Detector(calib, None)
    with caplog.at_level("INFO", logger="ko_monitor.detectors"):
        for _ in range(6):
            detector.detect(frame)
    messages = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    assert len(messages) == 3, messages
    assert "Notice" in messages[0]
    assert long_text[:120] in messages[1] and long_text[:121] not in messages[1]
    assert "None" in messages[2]


@pytest.mark.parametrize(
    "template, dialog, expected",
    [
        (None, None, None),
        (None, False, False),
        (False, None, False),
        (False, False, False),
        (True, False, True),
        (None, True, True),
        (False, True, True),
    ],
)
def test_dialog_flags_combine_template_and_dialog_text(calib, monkeypatch, template, dialog, expected):
    import ko_monitor.detectors as detectors

    monkeypatch.setattr(detectors, "read_hud", lambda frame, calib, ocr: (True, 9000, 9996, "Ronark Land"))
    monkeypatch.setattr(detectors, "read_inventory", lambda frame, inv, ocr: (None, None, None, None))
    monkeypatch.setattr(detectors, "read_chat", lambda frame, calib, ocr, tracker: [])
    monkeypatch.setattr(detectors, "template_present", lambda frame, spec: template)
    monkeypatch.setattr(detectors, "read_dialog", lambda frame, spec, ocr: ("Some text", dialog, dialog))
    width, height = calib.resolution
    r = Detector(calib, None).detect(np.zeros((height, width, 3), np.uint8))
    assert (r.revive_dialog, r.disconnect_dialog, r.dialog_text) == (expected, expected, "Some text")
