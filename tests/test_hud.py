import cv2
import numpy as np
import pytest

from helpers import sample_frames
from ko_monitor.detectors.hud import parse_ratio, parse_zone, read_hud


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("9718/9996", (9718, 9996)),
        ("0/9996", (0, 9996)),
        ("O/9996", (0, 9996)),
        ("9718 / 9996", (9718, 9996)),
        ("10/5", None),
        ("5/0", None),
        ("Lv 83", None),
        ("", None),
    ],
)
def test_parse_ratio(text, expected):
    assert parse_ratio(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ronark Land (428, 506)", "Ronark Land"),
        ("Moradon(12,34)", "Moradon"),
        ("Ronark Land", "Ronark Land"),
        ("   ", None),
    ],
)
def test_parse_zone(text, expected):
    assert parse_zone(text) == expected


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("normal"), ids=lambda p: p.name)
def test_read_hud_on_real_frames(path, calib, ocr):
    frame = cv2.imread(str(path))
    assert read_hud(frame, calib, ocr) == (True, 9718, 9996, "Ronark Land")


@pytest.mark.ocr
def test_read_hud_on_blank_frame(calib, ocr):
    frame = np.zeros((1440, 2560, 3), np.uint8)
    assert read_hud(frame, calib, ocr) == (False, None, None, None)
