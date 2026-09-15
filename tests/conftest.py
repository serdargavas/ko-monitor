import pytest

from helpers import ROOT


@pytest.fixture(scope="session")
def ocr():
    from ko_monitor.ocr import Ocr

    return Ocr(min_score=0.8)


@pytest.fixture(scope="session")
def calib():
    from ko_monitor.calibration import load_calibration

    return load_calibration(ROOT / "calibration.json")
