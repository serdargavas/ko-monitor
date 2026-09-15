from __future__ import annotations

import re

import cv2
import numpy as np

from ko_monitor.calibration import InventorySpec, crop
from ko_monitor.detectors.templates import load_template, template_present


def parse_money(text: str) -> int | None:
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def read_inventory(
    frame: np.ndarray, spec: InventorySpec | None, ocr
) -> tuple[bool | None, int | None, int | None, int | None]:
    """Returns (inventory_open, money, slots_used, slots_total); values only while the window is open."""
    if spec is None:
        return None, None, None, None
    is_open = template_present(frame, spec.window)
    if not is_open:
        return is_open, None, None, None

    money_line = ocr.read_line(crop(frame, spec.money_roi))
    money = parse_money(money_line[0]) if money_line else None

    empty = load_template(str(spec.empty_slot_file))
    if empty is None:
        return True, money, None, None
    width, height = spec.slot_size
    frame_h, frame_w = frame.shape[:2]
    cells = []
    for row in range(spec.rows):
        for col in range(spec.cols):
            x = spec.slot_origin[0] + col * spec.slot_step[0]
            y = spec.slot_origin[1] + row * spec.slot_step[1]
            if x < 0 or y < 0 or x + width > frame_w or y + height > frame_h:
                return True, money, None, None
            cells.append((x, y))
    used = 0
    for x, y in cells:
        cell = crop(frame, (x, y, width, height))
        if cell.shape[:2] != empty.shape[:2]:
            cell = cv2.resize(cell, (empty.shape[1], empty.shape[0]))
        if float(cv2.absdiff(cell, empty).mean()) > spec.empty_max_diff:
            used += 1
    return True, money, used, spec.cols * spec.rows
