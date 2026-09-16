import dataclasses
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.calibration import load_calibration
from ko_monitor.detectors.items import read_items
from ko_monitor.ocr import Ocr

CALIB = load_calibration(Path("calibration.json"))
ON = cv2.imread("samples/genie_on/20260916-153935.png")


@pytest.fixture(scope="module")
def ocr():
    return Ocr(min_score=CALIB.ocr_min_score)


def test_reads_arrow_and_mana_counts(ocr):
    arrow, mana = read_items(ON, True, CALIB.inventory, CALIB.items, ocr)
    assert arrow == 6380
    assert mana == 4150


def test_closed_inventory_reads_nothing(ocr):
    assert read_items(ON, False, CALIB.inventory, CALIB.items, ocr) == (None, None)


def test_missing_spec_reads_nothing(ocr):
    assert read_items(ON, True, CALIB.inventory, None, ocr) == (None, None)


def test_item_absent_from_every_slot_counts_as_zero(ocr):
    # No icon matches anywhere -> the stack is gone -> zero, which is what "bitti" means.
    blank = np.zeros_like(ON)
    assert read_items(blank, True, CALIB.inventory, CALIB.items, ocr) == (0, 0)


def test_slot_grid_off_frame_reads_nothing(ocr):
    small = ON[0:400, 0:400].copy()
    assert read_items(small, True, CALIB.inventory, CALIB.items, ocr) == (None, None)


def test_wrong_template_height_reads_nothing(ocr):
    # A re-cut template of the wrong size would otherwise silently fail every match, and "no
    # icon found anywhere" is deliberately reported as 0 -- which would fire a false "arrows are
    # gone" alarm. template_height must be load-bearing, not dead config.
    bad_spec = dataclasses.replace(CALIB.items, template_height=99)
    assert read_items(ON, True, CALIB.inventory, bad_spec, ocr) == (None, None)


def test_two_stacks_of_the_same_item_are_summed(ocr):
    # This committed frame carries two mana stacks (1197 and 5000) whose match scores differ only
    # by float noise. Keeping the best-scoring slot alone reports an arbitrary one of them: the
    # small stack is a false "running out" with 6197 potions in the bag, the big one never alerts
    # while the active stack empties.
    frame = cv2.imread("samples/inventory_open/20260915-133918.png")
    _, mana = read_items(frame, True, CALIB.inventory, CALIB.items, ocr)
    assert mana == 1197 + 5000


def test_unreadable_stack_count_reads_unknown(ocr):
    # A slot whose icon matches but whose number cannot be read must not contribute 0: that would
    # under-count the bag and fire a false alarm. The whole item reads as unknown instead.
    class NoDigits:
        def read_line(self, _image):
            return None

    assert read_items(ON, True, CALIB.inventory, CALIB.items, NoDigits()) == (None, None)
