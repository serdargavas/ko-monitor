import cv2
import pytest

from helpers import SAMPLES, sample_frames
from ko_monitor.calibration import crop
from ko_monitor.detectors import Detector
from ko_monitor.detectors.chat import classify, normalize


def detect(path, calib, ocr):
    readings = Detector(calib, ocr).detect(cv2.imread(str(path)))
    assert readings is not None, "frame resolution does not match calibration.json"
    return readings


def ids(path):
    return f"{path.parent.name}/{path.name}"


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("death"), ids=ids)
def test_death_samples(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.hp == 0 or r.revive_dialog is True


# 20260915-135013.png was saved the moment HP hit 0, before the dialog opened.
DEATH_DIALOG_FRAMES = [SAMPLES / "death" / name for name in ("20260915-135023.png", "20260915-135029.png")]


@pytest.mark.ocr
@pytest.mark.parametrize("path", DEATH_DIALOG_FRAMES, ids=ids)
def test_death_dialog_samples(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.revive_dialog is True
    assert r.disconnect_dialog is not True
    assert r.dialog_text is not None and "teleport" in r.dialog_text.lower()


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("disconnect"), ids=ids)
def test_disconnect_samples(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.login_screen is True or r.disconnect_dialog is True


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("inventory_open"), ids=ids)
def test_inventory_open_samples(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.inventory_open is True
    assert r.money is not None
    assert r.slots_used is not None and 0 <= r.slots_used <= r.slots_total


@pytest.mark.ocr
@pytest.mark.parametrize("path", sample_frames("inventory_full"), ids=ids)
def test_inventory_full_message_samples(path, calib, ocr):
    frame = cv2.imread(str(path))
    lines = [normalize(line.text) for line in ocr.read_block(crop(frame, calib.chat_roi))]
    assert "inventory_full" in classify(lines, calib.chat_phrases)


@pytest.mark.ocr
@pytest.mark.parametrize(
    "path",
    sample_frames("normal") + sample_frames("inventory_open") + sample_frames("inventory_full"),
    ids=ids,
)
def test_alive_samples_have_no_false_alarms(path, calib, ocr):
    r = detect(path, calib, ocr)
    assert r.hud_visible and r.hp > 0
    assert r.revive_dialog is not True
    assert r.login_screen is not True and r.disconnect_dialog is not True
    assert r.dialog_text is None
