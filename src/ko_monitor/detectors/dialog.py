from __future__ import annotations

import re

import numpy as np

from ko_monitor.calibration import DialogSpec, crop
from ko_monitor.detectors.templates import template_present

_FOLD = str.maketrans({
    "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g", "ş": "s", "Ş": "s",
    "ç": "c", "Ç": "c", "ö": "o", "Ö": "o", "ü": "u", "Ü": "u",
})


def fold(text: str) -> str:
    """Lowercase with Turkish letters folded to ASCII and whitespace collapsed."""
    return " ".join(text.translate(_FOLD).lower().split())


def _has_word_phrase(folded_text: str, phrase: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(fold(phrase)) + r"(?!\w)"
    return re.search(pattern, folded_text) is not None


DialogResult = tuple[str | None, bool | None, bool | None]


class DialogCache:
    """Last OCR result of an open dialog, keyed by the raw pixels of its text ROIs."""

    def __init__(self) -> None:
        self.key: tuple[bytes, ...] | None = None
        self.result: DialogResult | None = None

    def clear(self) -> None:
        self.key = None
        self.result = None


def read_dialog(
    frame: np.ndarray, spec: DialogSpec | None, ocr, cache: DialogCache | None = None
) -> DialogResult:
    """Returns (dialog_text, revive, disconnect) for the center dialog.

    Death and disconnect notices share the same dialog window, so the frame template only
    says "a dialog is open"; the text read from it decides which one it is. The dialog is
    translucent, so nameplates behind it can leak into the text: disconnect phrases (short,
    generic words) must match whole words and only in the first text line (lower lines often
    carry a nameplate); the long revive phrase and ignore phrases match the joined text as a
    substring.

    With a cache, OCR is skipped while the text ROI pixels are identical to the previous
    read of the still-open dialog; the cache is cleared when the dialog is not seen.
    """
    if spec is None:
        return None, None, None
    present = template_present(frame, spec.frame)
    if not present:
        if cache is not None:
            cache.clear()
        return (None, None, None) if present is None else (None, False, False)

    crops = [crop(frame, roi) for roi in spec.text_rois]
    key = tuple(part.tobytes() for part in crops)
    if cache is not None and cache.key == key:
        return cache.result
    result = _classify(crops, spec, ocr)
    if cache is not None:
        cache.key, cache.result = key, result
    return result


def _classify(crops: list[np.ndarray], spec: DialogSpec, ocr) -> DialogResult:
    lines = []
    for part in crops:
        line = ocr.read_line(part)
        lines.append(line[0].strip() if line is not None else "")
    text = " ".join(part for part in lines if part)
    folded = fold(text)
    first_line = fold(lines[0]) if lines else ""
    if any(fold(phrase) in folded for phrase in spec.ignore_phrases):
        return None, False, False
    revive = any(fold(phrase) in folded for phrase in spec.revive_phrases)
    disconnect = not revive and any(
        _has_word_phrase(first_line, phrase) for phrase in spec.disconnect_phrases
    )
    return text, revive, disconnect
