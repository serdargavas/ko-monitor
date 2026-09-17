"""How many arrows and mana potions are left.

Arrows and potions are found by their icon, not by a fixed slot, so moving them in the bag does
not break the count. The template is cut from the slot's top strip only: the stack count printed
across the bottom changes constantly and would ruin the match. The count itself is read from that
bottom strip with the same recognition-only OCR that reads HP and money.
"""

from __future__ import annotations

from typing import NamedTuple

import cv2
import numpy as np

from ko_monitor.calibration import InventorySpec, ItemsSpec
from ko_monitor.detectors.inventory import parse_money
from ko_monitor.detectors.templates import load_template

_COUNT_SCALE = 4  # the digits are ~14 px tall; OCR reads them reliably enlarged


class ItemReading(NamedTuple):
    """arrows/mana are None when they could not be read; arrow_unlimited replaces the arrow count."""

    arrows: int | None
    mana: int | None
    arrow_unlimited: bool = False
    scrolls: int | None = None


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


def _stack_count(frame: np.ndarray, cell: tuple[int, int], spec: ItemsSpec, ocr) -> int | None:
    """The number printed across one slot's bottom strip, or None when it cannot be read."""
    cx, cy, cw, ch = spec.count_box
    x, y = cell
    patch = frame[y + cy : y + cy + ch, x + cx : x + cx + cw]
    if patch.size == 0:
        return None
    big = cv2.resize(patch, (cw * _COUNT_SCALE, ch * _COUNT_SCALE), interpolation=cv2.INTER_CUBIC)
    line = ocr.read_line(big)
    return parse_money(line[0]) if line else None


def _present(
    frame: np.ndarray, cells: list[tuple[int, int]], template: np.ndarray, spec: ItemsSpec
) -> bool:
    """Is this icon in the bag at all? Used for items whose stack count means nothing."""
    t_h, t_w = template.shape[:2]
    for x, y in cells:
        patch = frame[y : y + t_h, x : x + t_w]
        if patch.shape[:2] != (t_h, t_w):
            continue
        score = float(np.nan_to_num(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED)).max())
        if score >= spec.match_threshold:
            return True
    return False


def _count_any(
    frame: np.ndarray,
    cells: list[tuple[int, int]],
    templates: list[np.ndarray],
    spec: ItemsSpec,
    ocr,
) -> int | None:
    """Counts an item that comes in several colours, matching colour-blind so a colour we have
    never seen still counts. Measured over every committed frame: in grayscale scrolls score
    0.82-1.00 and no other item passes 0.66, so the threshold sits between at 0.75. Matching in
    colour instead would miss every new colour the server adds.

    The caller narrows the cells to the row the player keeps them in: items elsewhere in the bag
    share this shape without being the scrolls that get sold.
    """
    if not templates:
        return None
    grays = [cv2.cvtColor(t, cv2.COLOR_BGR2GRAY) for t in templates]
    total, matched = 0, False
    for x, y in cells:
        best = 0.0
        for template in grays:
            t_h, t_w = template.shape[:2]
            patch = frame[y : y + t_h, x : x + t_w]
            if patch.shape[:2] != (t_h, t_w):
                continue
            gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
            score = float(np.nan_to_num(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)).max())
            best = max(best, score)
        if best < spec.scroll_threshold:
            continue
        matched = True
        count = _stack_count(frame, (x, y), spec, ocr)
        if count is None:
            return None
        total += count
    return total if matched else 0


def _count_of(
    frame: np.ndarray, cells: list[tuple[int, int]], template: np.ndarray, spec: ItemsSpec, ocr
) -> int | None:
    """Every matching stack added up: carrying two quivers is normal, and counting only the best
    slot is wrong in both directions - report the small stack and a full bag alerts as "running
    out", report the big one and no alert ever comes while the active quiver empties.
    """
    t_h, t_w = template.shape[:2]
    total, matched = 0, False
    for x, y in cells:
        patch = frame[y : y + t_h, x : x + t_w]
        if patch.shape[:2] != (t_h, t_w):
            continue
        score = float(np.nan_to_num(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED)).max())
        if score < spec.match_threshold:
            continue
        matched = True
        count = _stack_count(frame, (x, y), spec, ocr)
        if count is None:
            # A stack we can see but cannot read: adding the other slots alone would under-count
            # and fire a false "running out" alert, so the whole item reads as unknown and the
            # monitor keeps its last known value instead.
            return None
        total += count
    return total if matched else 0  # no icon anywhere: the stack is gone from the bag


def read_items(
    frame: np.ndarray,
    inventory_open: bool | None,
    inv: InventorySpec | None,
    spec: ItemsSpec | None,
    ocr,
) -> ItemReading:
    """Arrows and mana potions; both None while the bag is closed or nothing is calibrated."""
    if not inventory_open or inv is None or spec is None:
        return ItemReading(None, None)
    arrow_t = load_template(str(spec.arrow_file))
    mana_t = load_template(str(spec.mana_file))
    if arrow_t is None or mana_t is None:
        return ItemReading(None, None)
    # A re-cut template of the wrong size would silently fail every match, and "no icon found
    # anywhere" is deliberately reported as 0 — which would fire a false "arrows are gone" alarm.
    # Cross-check the loaded templates against the calibrated height so that mistake is loud.
    if arrow_t.shape[0] != spec.template_height or mana_t.shape[0] != spec.template_height:
        return ItemReading(None, None)
    cells = _slot_positions(frame, inv)
    if cells is None:
        return ItemReading(None, None)
    mana = _count_of(frame, cells, mana_t, spec, ocr)
    scroll_ts = [t for t in (load_template(str(f)) for f in spec.scroll_files) if t is not None]
    row_start = spec.scroll_row * inv.cols
    scroll_cells = cells[row_start : row_start + inv.cols]
    scrolls = _count_any(frame, scroll_cells, scroll_ts, spec, ocr)

    # The never-emptying quiver shows as a stack of 1, so counting it would alert forever. When it
    # is in the bag the arrow count is meaningless and no arrow alert should ever fire.
    unlimited_t = load_template(str(spec.arrow_unlimited_file)) if spec.arrow_unlimited_file else None
    if unlimited_t is not None and unlimited_t.shape[0] == spec.template_height:
        if _present(frame, cells, unlimited_t, spec):
            return ItemReading(None, mana, True, scrolls)
    return ItemReading(_count_of(frame, cells, arrow_t, spec, ocr), mana, False, scrolls)
