import numpy as np

from ko_monitor.detectors.frame_diff import FrameDiff


def test_frame_diff():
    diff = FrameDiff()
    a = np.zeros((1440, 2560, 3), np.uint8)
    b = np.full((1440, 2560, 3), 100, np.uint8)
    assert diff.update(a) is None
    assert diff.update(a) == 0.0
    assert diff.update(b) > 50
