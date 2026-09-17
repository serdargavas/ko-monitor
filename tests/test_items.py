import dataclasses
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.calibration import load_calibration
from ko_monitor.detectors.items import ItemReading, read_items
from ko_monitor.ocr import Ocr

CALIB = load_calibration(Path("calibration.json"))
ON = cv2.imread("samples/genie_on/20260916-153935.png")


@pytest.fixture(scope="module")
def ocr():
    return Ocr(min_score=CALIB.ocr_min_score)


def test_reads_arrow_and_mana_counts(ocr):
    arrow, mana, _ = read_items(ON, True, CALIB.inventory, CALIB.items, ocr)
    assert arrow == 6380
    assert mana == 4150


def test_closed_inventory_reads_nothing(ocr):
    assert read_items(ON, False, CALIB.inventory, CALIB.items, ocr) == ItemReading(None, None)


def test_missing_spec_reads_nothing(ocr):
    assert read_items(ON, True, CALIB.inventory, None, ocr) == ItemReading(None, None)


def test_item_absent_from_every_slot_counts_as_zero(ocr):
    # No icon matches anywhere -> the stack is gone -> zero, which is what "bitti" means.
    blank = np.zeros_like(ON)
    assert read_items(blank, True, CALIB.inventory, CALIB.items, ocr) == ItemReading(0, 0)


def test_slot_grid_off_frame_reads_nothing(ocr):
    small = ON[0:400, 0:400].copy()
    assert read_items(small, True, CALIB.inventory, CALIB.items, ocr) == ItemReading(None, None)


def test_wrong_template_height_reads_nothing(ocr):
    # A re-cut template of the wrong size would otherwise silently fail every match, and "no
    # icon found anywhere" is deliberately reported as 0 -- which would fire a false "arrows are
    # gone" alarm. template_height must be load-bearing, not dead config.
    bad_spec = dataclasses.replace(CALIB.items, template_height=99)
    assert read_items(ON, True, CALIB.inventory, bad_spec, ocr) == ItemReading(None, None)


def test_two_stacks_of_the_same_item_are_summed(ocr):
    # This committed frame carries two mana stacks (1197 and 5000) whose match scores differ only
    # by float noise. Keeping the best-scoring slot alone reports an arbitrary one of them: the
    # small stack is a false "running out" with 6197 potions in the bag, the big one never alerts
    # while the active stack empties.
    frame = cv2.imread("samples/inventory_open/20260915-133918.png")
    _, mana, _ = read_items(frame, True, CALIB.inventory, CALIB.items, ocr)
    assert mana == 1197 + 5000


def test_unreadable_stack_count_reads_unknown(ocr):
    # A slot whose icon matches but whose number cannot be read must not contribute 0: that would
    # under-count the bag and fire a false alarm. The whole item reads as unknown instead.
    class NoDigits:
        def read_line(self, _image):
            return None

    assert read_items(ON, True, CALIB.inventory, CALIB.items, NoDigits()) == ItemReading(None, None)


UNLIMITED = cv2.imread("samples/arrow_unlimited/20260917-100816.png")


def test_the_unlimited_quiver_replaces_the_arrow_count(ocr):
    # It shows as a stack of 1, so counting it would fire "arrows are low" forever.
    reading = read_items(UNLIMITED, True, CALIB.inventory, CALIB.items, ocr)
    assert reading.arrow_unlimited is True
    assert reading.arrows is None
    assert reading.mana == 5000 * 4 + 82  # the potions are still counted normally


def test_a_normal_quiver_is_not_mistaken_for_the_unlimited_one(ocr):
    reading = read_items(ON, True, CALIB.inventory, CALIB.items, ocr)
    assert reading.arrow_unlimited is False
    assert reading.arrows == 6380


def test_an_uncalibrated_unlimited_quiver_leaves_the_count_alone(ocr):
    spec = dataclasses.replace(CALIB.items, arrow_unlimited_file=None)
    reading = read_items(UNLIMITED, True, CALIB.inventory, spec, ocr)
    assert reading.arrow_unlimited is False
    assert reading.arrows == 0  # the old quiver really is gone from this bag
