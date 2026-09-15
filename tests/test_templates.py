from pathlib import Path

import cv2
import numpy as np

from ko_monitor.calibration import TemplateSpec
from ko_monitor.detectors.templates import template_present


def noisy_frame(seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 255, (300, 400, 3), dtype=np.uint8)


def write_template(tmp_path: Path, frame: np.ndarray) -> Path:
    path = tmp_path / "tpl.png"
    cv2.imwrite(str(path), frame[100:140, 200:260])
    return path


def test_present_inside_roi(tmp_path: Path):
    frame = noisy_frame()
    spec = TemplateSpec((180, 80, 120, 90), write_template(tmp_path, frame), 0.9)
    assert template_present(frame, spec) is True


def test_absent_elsewhere(tmp_path: Path):
    frame = noisy_frame()
    spec = TemplateSpec((0, 0, 150, 90), write_template(tmp_path, frame), 0.9)
    assert template_present(frame, spec) is False


def test_roi_smaller_than_template_is_absent(tmp_path: Path):
    frame = noisy_frame()
    spec = TemplateSpec((200, 100, 30, 20), write_template(tmp_path, frame), 0.9)
    assert template_present(frame, spec) is False


def test_unknown_when_not_calibrated(tmp_path: Path):
    frame = noisy_frame()
    assert template_present(frame, None) is None
    assert template_present(frame, TemplateSpec((0, 0, 10, 10), tmp_path / "missing.png", 0.9)) is None
