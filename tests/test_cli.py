import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from helpers import ROOT
from ko_monitor.cli import build_parser, main, parse_roi, run_config_warnings
from ko_monitor.config import Config, HeartbeatConfig


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


def test_default_config_is_in_the_project_root():
    assert build_parser().parse_args(["vapid"]).config == ROOT / "config.toml"


@pytest.mark.parametrize(
    "text",
    [
        "[general\nprocess_name = 1\n",
        "[thresholds]\nno_such_threshold = 1\n",
        '[api]\nstream_quality = "ultra"\n',
    ],
)
def test_malformed_config_is_a_one_line_error(tmp_path: Path, capsys, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    image = tmp_path / "in.png"
    cv2.imwrite(str(image), np.zeros((10, 10, 3), np.uint8))
    code = main(["--config", str(path), "crop", str(image), "--roi", "0,0,1,1", "--out", str(tmp_path / "o.png")])
    err = capsys.readouterr().err
    assert code == 2
    assert str(path) in err
    assert err.strip() and "\n" not in err.strip()
    assert "Traceback" not in err


UUID_URL = "https://hc-ping.com/0f3c2a1e-9b7d-4c55-8e21-6a4b3c2d1e0f"


def test_run_config_warnings(tmp_path: Path):
    missing = tmp_path / "config.toml"
    warnings = run_config_warnings(Config(), missing)
    assert len(warnings) == 2
    assert str(missing) in warnings[0]
    assert "ping_url" in warnings[1]

    present = tmp_path / "present.toml"
    present.write_text("", encoding="utf-8")
    ok = Config(heartbeat=HeartbeatConfig(ping_url=UUID_URL, api_key="key"))
    assert run_config_warnings(ok, present) == []
    assert run_config_warnings(Config(heartbeat=HeartbeatConfig(ping_url=UUID_URL)), present) == []

    slug = Config(heartbeat=HeartbeatConfig(ping_url="https://hc-ping.com/pingkey/my-check", api_key="key"))
    other_host = Config(heartbeat=HeartbeatConfig(ping_url="https://example.com/" + UUID_URL[-36:], api_key="key"))
    for cfg in (slug, other_host):
        warnings = run_config_warnings(cfg, present)
        assert len(warnings) == 1 and "pause" in warnings[0]
    assert run_config_warnings(Config(heartbeat=HeartbeatConfig(ping_url="https://hc-ping.com/pingkey/my-check")), present) == []


def test_ocr_command_survives_characters_outside_the_console_code_page(tmp_path: Path, monkeypatch, capsys):
    """On Windows the console defaults to a legacy code page (e.g. cp1254); OCR text
    containing characters outside it used to crash `ocr` with UnicodeEncodeError."""
    import ko_monitor.ocr as ocr_module
    from ko_monitor.ocr import OcrLine

    class FakeOcr:
        def __init__(self, min_score=0.0):
            pass

        def read_block(self, image):
            return [OcrLine("福", 0.99, (0, 0, 10, 10))]

    monkeypatch.setattr(ocr_module, "Ocr", FakeOcr)
    # capsys's own capture stream may or may not support reconfigure depending on capture mode.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="cp1254", errors="strict")

    image = tmp_path / "in.png"
    cv2.imwrite(str(image), np.zeros((10, 10, 3), np.uint8))

    code = main(["--config", str(tmp_path / "none.toml"), "ocr", str(image)])

    out = capsys.readouterr().out
    assert code == 0
    assert "福" in out
