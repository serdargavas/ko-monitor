import argparse
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.cli import main, parse_roi


def test_parse_roi():
    assert parse_roi("1, 2,3,4") == (1, 2, 3, 4)
    with pytest.raises(argparse.ArgumentTypeError):
        parse_roi("1,2,3")


def test_crop_command(tmp_path: Path):
    image = tmp_path / "in.png"
    cv2.imwrite(str(image), np.zeros((100, 200, 3), np.uint8))
    out = tmp_path / "templates" / "out.png"
    assert main(["--config", str(tmp_path / "none.toml"), "crop", str(image), "--roi", "10,20,30,40", "--out", str(out)]) == 0
    assert cv2.imread(str(out)).shape == (40, 30, 3)
