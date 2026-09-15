from __future__ import annotations

import re

import numpy as np

from ko_monitor.calibration import Calibration, crop
from ko_monitor.ocr import Ocr

_RATIO = re.compile(r"^(\d{1,7})/(\d{1,7})$")
_ZONE = re.compile(r"^(.*?)\s*\(\s*\d+\s*,\s*\d+\s*\)\s*$")
_DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "D": "0"})


def parse_ratio(text: str) -> tuple[int, int] | None:
    match = _RATIO.match(text.replace(" ", "").translate(_DIGIT_FIXES))
    if not match:
        return None
    current, maximum = int(match.group(1)), int(match.group(2))
    if maximum == 0 or current > maximum:
        return None
    return current, maximum


def parse_zone(text: str) -> str | None:
    text = text.strip()
    match = _ZONE.match(text)
    name = (match.group(1) if match else text).strip()
    return name or None


def read_hud(
    frame: np.ndarray, calib: Calibration, ocr: Ocr
) -> tuple[bool, int | None, int | None, str | None]:
    """Returns (hud_visible, hp, hp_max, zone). HUD counts as visible when HP text parses."""
    hp_line = ocr.read_line(crop(frame, calib.hp_roi))
    ratio = parse_ratio(hp_line[0]) if hp_line else None
    if ratio is None:
        return False, None, None, None
    zone_line = ocr.read_line(crop(frame, calib.zone_roi))
    zone = parse_zone(zone_line[0]) if zone_line else None
    return True, ratio[0], ratio[1], zone
