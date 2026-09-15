from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.capture import ReplaySource, is_black
from ko_monitor.models import CaptureStatus


def test_is_black():
    assert is_black(np.zeros((1440, 2560, 3), np.uint8))
    frame = np.zeros((1440, 2560, 3), np.uint8)
    frame[:, :400] = 120  # ~16% bright pixels
    assert not is_black(frame)


def test_replay_serves_files_in_name_order_then_repeats_last(tmp_path: Path):
    for name, value in (("b.png", 200), ("a.png", 100)):
        cv2.imwrite(str(tmp_path / name), np.full((20, 30, 3), value, np.uint8))
    source = ReplaySource(tmp_path)
    status, first = source.latest()
    assert status == CaptureStatus.OK and first[0, 0, 0] == 100
    assert not source.exhausted
    _, second = source.latest()
    assert second[0, 0, 0] == 200
    assert source.exhausted
    _, again = source.latest()
    assert again[0, 0, 0] == 200


def test_replay_marks_black_frames(tmp_path: Path):
    cv2.imwrite(str(tmp_path / "x.png"), np.zeros((20, 30, 3), np.uint8))
    assert ReplaySource(tmp_path).latest()[0] == CaptureStatus.BLACK


def test_replay_requires_frames(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ReplaySource(tmp_path)
