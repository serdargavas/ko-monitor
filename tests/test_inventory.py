from pathlib import Path

import cv2
import numpy as np

from ko_monitor.calibration import InventorySpec, TemplateSpec
from ko_monitor.detectors.inventory import parse_money, read_inventory


class FakeOcr:
    def __init__(self, text: str | None):
        self.text = text

    def read_line(self, image):
        return None if self.text is None else (self.text, 0.99)


def test_parse_money():
    assert parse_money("1,234,567") == 1234567
    assert parse_money("12.500 Coins") == 12500
    assert parse_money("Coins") is None


def build(tmp_path: Path, with_window: bool = True):
    rng = np.random.default_rng(7)
    frame = np.full((300, 400, 3), 30, np.uint8)
    window = rng.integers(0, 255, (20, 60, 3), dtype=np.uint8)
    if with_window:
        frame[10:30, 10:70] = window
    empty = np.full((20, 20, 3), 50, np.uint8)
    empty[0, :] = empty[:, 0] = 90  # slot border
    for row in range(2):
        for col in range(2):
            frame[100 + row * 25 : 120 + row * 25, 100 + col * 25 : 120 + col * 25] = empty
    frame[100:120, 125:145] = rng.integers(0, 255, (20, 20, 3), dtype=np.uint8)  # item in slot (0,1)
    cv2.imwrite(str(tmp_path / "window.png"), window)
    cv2.imwrite(str(tmp_path / "empty.png"), empty)
    spec = InventorySpec(
        window=TemplateSpec((0, 0, 100, 50), tmp_path / "window.png", 0.9),
        money_roi=(200, 200, 80, 16),
        slot_origin=(100, 100), slot_size=(20, 20), slot_step=(25, 25), cols=2, rows=2,
        empty_slot_file=tmp_path / "empty.png", empty_max_diff=10.0,
    )
    return frame, spec


def test_not_calibrated():
    frame = np.zeros((10, 10, 3), np.uint8)
    assert read_inventory(frame, None, FakeOcr("1")) == (None, None, None, None)


def test_window_closed(tmp_path: Path):
    frame, spec = build(tmp_path, with_window=False)
    assert read_inventory(frame, spec, FakeOcr("1")) == (False, None, None, None)


def test_open_window_reads_money_and_slots(tmp_path: Path):
    frame, spec = build(tmp_path)
    assert read_inventory(frame, spec, FakeOcr("1,500,000")) == (True, 1500000, 1, 4)


def test_open_window_unreadable_money(tmp_path: Path):
    frame, spec = build(tmp_path)
    assert read_inventory(frame, spec, FakeOcr(None)) == (True, None, 1, 4)
