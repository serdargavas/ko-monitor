import dataclasses
from pathlib import Path

import cv2
import numpy as np

from ko_monitor.calibration import DialogSpec, TemplateSpec
from ko_monitor.detectors.dialog import DialogCache, read_dialog


class FakeOcr:
    """Returns the given lines in order, one per read_line call (None = nothing read)."""

    def __init__(self, lines: list[str | None]):
        self.lines = list(lines)
        self.calls = 0

    def read_line(self, image):
        text = self.lines[self.calls] if self.calls < len(self.lines) else None
        self.calls += 1
        return None if text is None else (text, 0.99)


def build(tmp_path: Path, with_frame: bool = True, template_on_disk: bool = True):
    rng = np.random.default_rng(11)
    frame = rng.integers(0, 255, (200, 300, 3), dtype=np.uint8)
    ornament = rng.integers(0, 255, (20, 30, 3), dtype=np.uint8)
    if with_frame:
        frame[10:30, 20:50] = ornament
    if template_on_disk:
        cv2.imwrite(str(tmp_path / "dialog_frame.png"), ornament)
    spec = DialogSpec(
        frame=TemplateSpec((0, 0, 80, 60), tmp_path / "dialog_frame.png", 0.9),
        text_rois=((50, 100, 200, 16), (50, 120, 200, 16)),
        revive_phrases=["teleport back to the re-spawn"],
        disconnect_phrases=["disconnect", "server"],
        ignore_phrases=["party invitation"],
    )
    return frame, spec


def test_not_calibrated():
    frame = np.zeros((10, 10, 3), np.uint8)
    assert read_dialog(frame, None, FakeOcr(["x"])) == (None, None, None)


def test_template_missing_on_disk(tmp_path: Path):
    frame, spec = build(tmp_path, template_on_disk=False)
    assert read_dialog(frame, spec, FakeOcr(["x"])) == (None, None, None)


def test_frame_absent(tmp_path: Path):
    frame, spec = build(tmp_path, with_frame=False)
    ocr = FakeOcr(["Disconnected"])
    assert read_dialog(frame, spec, ocr) == (None, False, False)
    assert ocr.calls == 0


def test_revive_text(tmp_path: Path):
    frame, spec = build(tmp_path)
    ocr = FakeOcr(["Press OK to teleport back to the re-spawn p", " oint. "])
    assert read_dialog(frame, spec, ocr) == ("Press OK to teleport back to the re-spawn p oint.", True, False)
    assert ocr.calls == 2


def test_disconnect_text(tmp_path: Path):
    frame, spec = build(tmp_path)
    assert read_dialog(frame, spec, FakeOcr(["Disconnected from Server", None])) == (
        "Disconnected from Server", False, True,
    )


def test_revive_wins_over_disconnect_phrase(tmp_path: Path):
    frame, spec = build(tmp_path)
    ocr = FakeOcr(["Teleport back to the re-spawn point", "server"])
    assert read_dialog(frame, spec, ocr) == ("Teleport back to the re-spawn point server", True, False)


def test_unknown_text(tmp_path: Path):
    frame, spec = build(tmp_path)
    assert read_dialog(frame, spec, FakeOcr(["  Something happened ", None])) == (
        "Something happened", False, False,
    )


def test_ignored_text(tmp_path: Path):
    frame, spec = build(tmp_path)
    assert read_dialog(frame, spec, FakeOcr(["Party Invitation from X", "Accept?"])) == (None, False, False)


def test_ocr_reads_nothing_is_still_a_dialog(tmp_path: Path):
    frame, spec = build(tmp_path)
    assert read_dialog(frame, spec, FakeOcr([None, None])) == ("", False, False)


def test_disconnect_phrase_matches_whole_words_only(tmp_path: Path):
    frame, spec = build(tmp_path)
    # A nameplate behind the translucent dialog must not match "server" inside another word.
    ocr = FakeOcr(["Unexpected notice", "[Observers] Serverus"])
    assert read_dialog(frame, spec, ocr) == ("Unexpected notice [Observers] Serverus", False, False)


def test_disconnect_phrase_matches_multiword_phrase(tmp_path: Path):
    frame, spec = build(tmp_path)
    spec = dataclasses.replace(spec, disconnect_phrases=["connection lost"])
    assert read_dialog(frame, spec, FakeOcr(["The Connection  lost.", None])) == (
        "The Connection  lost.", False, True,
    )


def test_turkish_letters_are_folded_before_matching(tmp_path: Path):
    frame, spec = build(tmp_path)
    spec = dataclasses.replace(
        spec, disconnect_phrases=["bağlantı", "sunucu"], ignore_phrases=["parti daveti"]
    )
    assert read_dialog(frame, spec, FakeOcr(["BAĞLANTI KOPTU", None])) == ("BAĞLANTI KOPTU", False, True)
    assert read_dialog(frame, spec, FakeOcr(["Baglanti koptu", None])) == ("Baglanti koptu", False, True)
    assert read_dialog(frame, spec, FakeOcr(["PARTİ DAVETİ", None])) == (None, False, False)


def test_disconnect_phrase_only_in_line_two_is_unknown(tmp_path: Path):
    frame, spec = build(tmp_path)
    # Line 2 often carries a nameplate leaking through the translucent dialog.
    ocr = FakeOcr(["Unexpected notice", "Server Guard"])
    assert read_dialog(frame, spec, ocr) == ("Unexpected notice Server Guard", False, False)


def test_disconnect_phrase_in_line_one_is_disconnect(tmp_path: Path):
    frame, spec = build(tmp_path)
    ocr = FakeOcr(["Lost the server", "Guard"])
    assert read_dialog(frame, spec, ocr) == ("Lost the server Guard", False, True)


class CountingOcr:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def read_line(self, image):
        self.calls += 1
        return self.text, 0.99


def test_static_dialog_skips_ocr(tmp_path: Path):
    frame, spec = build(tmp_path)
    ocr = CountingOcr("Server lost")
    cache = DialogCache()
    first = read_dialog(frame, spec, ocr, cache)
    assert first == ("Server lost Server lost", False, True)
    assert ocr.calls == 2
    assert read_dialog(frame.copy(), spec, ocr, cache) == first
    assert ocr.calls == 2


def test_changed_text_pixels_run_ocr_again(tmp_path: Path):
    frame, spec = build(tmp_path)
    ocr = CountingOcr("Something")
    cache = DialogCache()
    read_dialog(frame, spec, ocr, cache)
    changed = frame.copy()
    changed[125, 60] = changed[125, 60] ^ 0xFF  # inside the second text ROI
    ocr.text = "Server down"
    assert read_dialog(changed, spec, ocr, cache) == ("Server down Server down", False, True)
    assert ocr.calls == 4


def test_dialog_gone_resets_the_cache(tmp_path: Path):
    frame, spec = build(tmp_path)
    without_frame, _ = build(tmp_path, with_frame=False)
    # Same text pixels in both frames: only the dialog frame ornament differs.
    without_frame[100:140] = frame[100:140]
    ocr = CountingOcr("Something")
    cache = DialogCache()
    read_dialog(frame, spec, ocr, cache)
    assert read_dialog(without_frame, spec, ocr, cache) == (None, False, False)
    assert ocr.calls == 2
    read_dialog(frame, spec, ocr, cache)
    assert ocr.calls == 4


def test_without_cache_ocr_runs_every_time(tmp_path: Path):
    frame, spec = build(tmp_path)
    ocr = CountingOcr("Something")
    read_dialog(frame, spec, ocr)
    read_dialog(frame, spec, ocr)
    assert ocr.calls == 4


def test_revive_phrase_still_matches_as_substring_after_folding(tmp_path: Path):
    frame, spec = build(tmp_path)
    ocr = FakeOcr(["Press OK to TELEPORT BACK TO THE RE-SPAWN p", "oint."])
    assert read_dialog(frame, spec, ocr)[1:] == (True, False)
