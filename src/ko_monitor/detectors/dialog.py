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


def read_dialog(
    frame: np.ndarray, spec: DialogSpec | None, ocr
) -> tuple[str | None, bool | None, bool | None]:
    """Returns (dialog_text, revive, disconnect) for the center dialog.

    Death and disconnect notices share the same dialog window, so the frame template only
    says "a dialog is open"; the text read from it decides which one it is. The dialog is
    translucent, so nameplates behind it can leak into the text: disconnect phrases (short,
    generic words) must match whole words; the long revive phrase matches as a substring.
    """
    if spec is None:
        return None, None, None
    present = template_present(frame, spec.frame)
    if present is None:
        return None, None, None
    if not present:
        return None, False, False

    parts = []
    for roi in spec.text_rois:
        line = ocr.read_line(crop(frame, roi))
        if line is not None and line[0].strip():
            parts.append(line[0].strip())
    text = " ".join(parts)
    folded = fold(text)
    if any(fold(phrase) in folded for phrase in spec.ignore_phrases):
        return None, False, False
    revive = any(fold(phrase) in folded for phrase in spec.revive_phrases)
    disconnect = not revive and any(_has_word_phrase(folded, phrase) for phrase in spec.disconnect_phrases)
    return text, revive, disconnect
