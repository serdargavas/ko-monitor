import json
from pathlib import Path

import cv2
import numpy as np

from ko_monitor.calibration import crop, load_calibration


def test_repo_calibration_loads(calib):
    assert calib.resolution == (2560, 1440)
    assert calib.hp_roi == (60, 34, 130, 16)
    assert calib.templates == {}
    assert calib.inventory is not None
    assert (calib.inventory.cols, calib.inventory.rows) == (7, 4)
    assert calib.chat_phrases == {"inventory_full": []}


def test_repo_calibration_has_dialog_block(calib):
    dialog = calib.dialog
    assert dialog is not None
    assert dialog.frame.file.name == "dialog_frame.png" and dialog.frame.file.exists()
    assert len(dialog.text_rois) == 2
    assert all(len(roi) == 4 for roi in dialog.text_rois)
    assert "teleport back to the re-spawn" in dialog.revive_phrases
    assert "disconnect" in dialog.disconnect_phrases
    phrases = dialog.revive_phrases + dialog.disconnect_phrases + dialog.ignore_phrases
    assert all(p == p.lower() for p in phrases)


def test_dialog_block_is_optional(tmp_path: Path):
    data = {"resolution": [2560, 1440], "hp_roi": [1, 2, 3, 4], "zone_roi": [1, 2, 3, 4], "chat_roi": [1, 2, 3, 4]}
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    c = load_calibration(path)
    assert c.dialog is None and c.inventory is None


def test_paths_resolve_relative_to_file_and_phrases_lowercase(tmp_path: Path):
    data = {
        "resolution": [2560, 1440],
        "hp_roi": [1, 2, 3, 4], "zone_roi": [1, 2, 3, 4], "chat_roi": [1, 2, 3, 4],
        "chat_phrases": {"inventory_full": ["Inventory Is FULL"]},
        "templates": {"revive_dialog": {"roi": [10, 20, 30, 40], "file": "templates/r.png", "threshold": 0.9}},
        "inventory": {
            "window": {"roi": [0, 0, 5, 5], "file": "templates/inv.png", "threshold": 0.8},
            "money_roi": [1, 1, 2, 2], "slot_origin": [100, 200], "slot_size": [40, 40],
            "slot_step": [45, 45], "cols": 7, "rows": 4,
            "empty_slot_file": "templates/empty.png", "empty_max_diff": 12,
        },
        "dialog": {
            "frame": {"roi": [5, 6, 7, 8], "file": "templates/dialog.png", "threshold": 0.85},
            "text_rois": [[1, 2, 3, 4], [5, 6, 7, 8]],
            "revive_phrases": ["Teleport BACK"],
            "disconnect_phrases": ["Disconnect", "BAĞLANTI"],
            "ignore_phrases": ["Party Invite"],
        },
    }
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    c = load_calibration(path)
    assert c.black_threshold == 0.95 and c.ocr_min_score == 0.8
    assert c.chat_phrases == {"inventory_full": ["inventory is full"]}
    assert c.templates["revive_dialog"].file == tmp_path / "templates" / "r.png"
    assert c.templates["revive_dialog"].roi == (10, 20, 30, 40)
    assert c.inventory.cols * c.inventory.rows == 28
    assert c.inventory.empty_slot_file == tmp_path / "templates" / "empty.png"
    assert c.dialog.frame.file == tmp_path / "templates" / "dialog.png"
    assert (c.dialog.frame.roi, c.dialog.frame.threshold) == ((5, 6, 7, 8), 0.85)
    assert c.dialog.text_rois == ((1, 2, 3, 4), (5, 6, 7, 8))
    assert c.dialog.revive_phrases == ["teleport back"]
    assert c.dialog.disconnect_phrases == ["disconnect", "bağlanti"]
    assert c.dialog.ignore_phrases == ["party invite"]


def test_crop():
    frame = np.arange(100 * 200 * 3, dtype=np.uint32).reshape(100, 200, 3)
    part = crop(frame, (10, 20, 30, 40))
    assert part.shape == (40, 30, 3)
    assert (part[0, 0] == frame[20, 10]).all()


def test_genie_spec_is_loaded(tmp_path):
    calib = load_calibration(Path("calibration.json"))
    assert calib.genie is not None
    assert calib.genie.stop_box == (2511, 9, 12, 13)
    assert calib.genie.play_box == (2482, 9, 14, 14)
    assert calib.genie.margin == 60.0
    assert calib.genie.header_at == (2330, 0)
    assert calib.genie.header.roi == (2200, 0, 360, 220)
    assert calib.genie.header.file.name == "genie_header.png"
    # A threshold silently loosened to hide a decaying template would turn "panel not found"
    # into a confident wrong answer, and the panel is what decides whether a death is reported.
    assert calib.genie.header.threshold == 0.8


def test_genie_header_template_excludes_the_countdown(tmp_path):
    """The committed template must be the title strip only. The "Time Left : N Hour(s)" line
    below it changes, and with it inside the template the match on other frames fell to 0.79 -
    under the 0.8 threshold - which reads as "no panel" = genie unknown."""
    calib = load_calibration(Path("calibration.json"))
    template = cv2.imread(str(calib.genie.header.file))
    assert template is not None
    assert template.shape[:2] == (30, 230)
    for sample in ("samples/genie_on/20260916-153935.png", "samples/genie_off/20260916-154450.png"):
        frame = cv2.imread(sample)
        x, y, w, h = calib.genie.header.roi
        scores = cv2.matchTemplate(frame[y : y + h, x : x + w], template, cv2.TM_CCOEFF_NORMED)
        assert scores.max() >= 0.95, sample


def test_items_spec_is_loaded():
    calib = load_calibration(Path("calibration.json"))
    assert calib.items is not None
    assert calib.items.match_threshold == 0.85
    assert calib.items.count_box == (1, 28, 30, 16)
    assert calib.items.template_height == 27
    assert calib.items.arrow_file.name == "item_arrow.png"
    assert calib.items.mana_file.name == "item_mana.png"


def test_genie_and_items_are_optional(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({
        "resolution": [2560, 1440], "hp_roi": [0, 0, 1, 1],
        "zone_roi": [0, 0, 1, 1], "chat_roi": [0, 0, 1, 1],
    }), encoding="utf-8")
    calib = load_calibration(path)
    assert calib.genie is None and calib.items is None
