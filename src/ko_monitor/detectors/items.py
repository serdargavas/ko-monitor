"""How many arrows and mana potions are left.

Arrows and potions are found by their icon, not by a fixed slot, so moving them in the bag does
not break the count. The template is cut from the slot's top strip only: the stack count printed
across the bottom changes constantly and would ruin the match. The count itself is read from that
bottom strip with the same recognition-only OCR that reads HP and money.
"""

from __future__ import annotations

import cv2
import numpy as np

from ko_monitor.calibration import InventorySpec, ItemsSpec
from ko_monitor.detectors.inventory import parse_money
from ko_monitor.detectors.templates import load_template

_COUNT_SCALE = 4  # the digits are ~14 px tall; OCR reads them reliably enlarged


def _slot_positions(frame: np.ndarray, inv: InventorySpec) -> list[tuple[int, int]] | None:
    """Every slot's top-left corner, or None when the grid does not fit the frame."""
    width = inv.slot_size[0]
    frame_h, frame_w = frame.shape[:2]
    cells = []
    for row in range(inv.rows):
        for col in range(inv.cols):
            x = inv.slot_origin[0] + col * inv.slot_step[0]
            y = inv.slot_origin[1] + row * inv.slot_step[1]
            if x < 0 or y < 0 or x + width > frame_w or y + inv.slot_size[1] > frame_h:
                return None
            cells.append((x, y))
    return cells


def _count_of(
    frame: np.ndarray, cells: list[tuple[int, int]], template: np.ndarray, spec: ItemsSpec, ocr
) -> int | None:
    best_score, best_cell = -1.0, None
    t_h, t_w = template.shape[:2]
    for x, y in cells:
        patch = frame[y : y + t_h, x : x + t_w]
        if patch.shape[:2] != (t_h, t_w):
            continue
        score = float(np.nan_to_num(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED)).max())
        if score > best_score:
            best_score, best_cell = score, (x, y)
    if best_cell is None or best_score < spec.match_threshold:
        return 0  # the stack is gone from the bag: nothing left
    cx, cy, cw, ch = spec.count_box
    x, y = best_cell
    patch = frame[y + cy : y + cy + ch, x + cx : x + cx + cw]
    if patch.size == 0:
        return None
    big = cv2.resize(patch, (cw * _COUNT_SCALE, ch * _COUNT_SCALE), interpolation=cv2.INTER_CUBIC)
    line = ocr.read_line(big)
    return parse_money(line[0]) if line else None


def read_items(
    frame: np.ndarray,
    inventory_open: bool | None,
    inv: InventorySpec | None,
    spec: ItemsSpec | None,
    ocr,
) -> tuple[int | None, int | None]:
    """(arrows, mana potions); both None while the bag is closed or nothing is calibrated."""
    if not inventory_open or inv is None or spec is None:
        return None, None
    arrow_t = load_template(str(spec.arrow_file))
    mana_t = load_template(str(spec.mana_file))
    if arrow_t is None or mana_t is None:
        return None, None
    # A re-cut template of the wrong size would silently fail every match, and "no icon found
    # anywhere" is deliberately reported as 0 — which would fire a false "arrows are gone" alarm.
    # Cross-check the loaded templates against the calibrated height so that mistake is loud.
    if arrow_t.shape[0] != spec.template_height or mana_t.shape[0] != spec.template_height:
        return None, None
    cells = _slot_positions(frame, inv)
    if cells is None:
        return None, None
    return (
        _count_of(frame, cells, arrow_t, spec, ocr),
        _count_of(frame, cells, mana_t, spec, ocr),
    )
