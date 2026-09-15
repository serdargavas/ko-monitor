import pytest

from helpers import SAMPLES
from ko_monitor.agent import run_replay
from ko_monitor.config import Config
from ko_monitor.detectors import Detector
from ko_monitor.storage import Storage


@pytest.mark.ocr
def test_replay_of_normal_frames(tmp_path, calib, ocr):
    storage = Storage(tmp_path / "replay.sqlite3")
    events = run_replay(Config(data_dir=tmp_path), SAMPLES / "normal", Detector(calib, ocr), storage)
    assert [e["kind"] for e in events] == ["game_started", "game_closed"]
    snapshots = storage.snapshots_since(0)
    assert len(snapshots) == 1
    assert (snapshots[0].state.value, snapshots[0].hp, snapshots[0].zone) == ("alive", 9718, "Ronark Land")
    storage.close()
