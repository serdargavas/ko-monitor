from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.calibration import GenieSpec, TemplateSpec, load_calibration
from ko_monitor.detectors.genie import read_genie

CALIB = load_calibration(Path("calibration.json"))
ON = cv2.imread("samples/genie_on/20260916-153935.png")
OFF = cv2.imread("samples/genie_off/20260916-154450.png")


def test_running_genie_is_detected():
    assert read_genie(ON, CALIB.genie) is True


def test_stopped_genie_is_detected():
    assert read_genie(OFF, CALIB.genie) is False


def test_no_spec_is_unknown():
    assert read_genie(ON, None) is None


def test_missing_panel_is_unknown():
    # A frame with no Genie panel at all: the header template cannot be found.
    blank = np.zeros_like(ON)
    assert read_genie(blank, CALIB.genie) is None


def test_moved_panel_is_still_read(tmp_path):
    # The user dragged the panel 40 px left and 12 px down; the boxes must follow the header.
    moved = np.zeros_like(ON)
    src = ON[0:200, 2300:2560]
    moved[12:212, 2260:2520] = src
    assert read_genie(moved, CALIB.genie) is True


def test_unclear_buttons_are_unknown():
    # Both boxes equally saturated (panel found, buttons washed out) -> no verdict.
    flat = ON.copy()
    spec = CALIB.genie
    for box in (spec.stop_box, spec.play_box):
        x, y, w, h = box
        flat[y : y + h, x : x + w] = (40, 40, 40)
    assert read_genie(flat, spec) is None
