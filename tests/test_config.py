from pathlib import Path

import pytest

from helpers import ROOT
from ko_monitor.config import ApiConfig, Config, load_config


def test_defaults_when_file_missing(tmp_path: Path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.process_name == "Client.acme"
    assert cfg.window_title == "Knight Evolution"
    assert cfg.thresholds.tick_s == 2.0
    assert cfg.thresholds.disconnect_soft_s == 15.0
    assert cfg.heartbeat.ping_url == ""


def test_none_path_gives_defaults():
    assert load_config(None).thresholds.blind_s == 60.0


def test_overrides_are_merged_with_defaults(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[general]\nwindow_title = "Other"\ndata_dir = "D:/kodata"\n'
        "[thresholds]\nfrozen_s = 30\n"
        '[heartbeat]\nping_url = "https://hc-ping.com/abc"\n',
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.window_title == "Other"
    assert cfg.data_dir == Path("D:/kodata")
    assert cfg.thresholds.frozen_s == 30
    assert cfg.thresholds.blind_s == 60.0
    assert cfg.heartbeat.ping_url == "https://hc-ping.com/abc"
    assert cfg.push.max_age_s == 300.0


def test_relative_paths_resolve_against_the_config_folder(tmp_path: Path):
    folder = tmp_path / "conf"
    folder.mkdir()
    path = folder / "config.toml"
    path.write_text('[general]\ndata_dir = "mydata"\ncalibration_path = "calib/c.json"\n', encoding="utf-8")
    cfg = load_config(path, tmp_path / "elsewhere")
    base = folder.resolve()
    assert cfg.data_dir == base / "mydata"
    assert cfg.log_dir == base / "logs"
    assert cfg.calibration_path == base / "calib" / "c.json"


def test_relative_paths_resolve_against_base_dir_when_file_missing(tmp_path: Path):
    cfg = load_config(tmp_path / "missing.toml", tmp_path)
    assert cfg.data_dir == tmp_path / "data"
    assert cfg.log_dir == tmp_path / "logs"
    assert cfg.calibration_path == tmp_path / "calibration.json"


def test_default_base_dir_is_the_project_root():
    assert load_config(None).calibration_path == ROOT / "calibration.json"


def test_api_defaults_and_overrides(tmp_path: Path):
    assert load_config(None).api == ApiConfig(port=8765, stream_quality="medium")
    path = tmp_path / "config.toml"
    path.write_text('[api]\nport = 9000\nstream_quality = "high"\n', encoding="utf-8")
    assert load_config(path).api == ApiConfig(port=9000, stream_quality="high")


@pytest.mark.parametrize("text", ['[api]\nstream_quality = "ultra"\n', "[api]\nport = 0\n", "[api]\nport = 70000\n"])
def test_invalid_api_settings_raise_value_error(tmp_path: Path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_item_thresholds_have_defaults():
    t = Config().thresholds
    assert (t.arrow_low, t.mana_low) == (1000, 200)
    assert t.item_low_repeat_s == 600.0
    assert t.income_max_jump == 50_000_000
