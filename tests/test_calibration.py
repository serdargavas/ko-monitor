import json
from pathlib import Path

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
