from __future__ import annotations

import numpy as np

from ko_monitor.calibration import DialogSpec, crop
from ko_monitor.detectors.templates import template_present


def read_dialog(
    frame: np.ndarray, spec: DialogSpec | None, ocr
) -> tuple[str | None, bool | None, bool | None]:
    """Returns (dialog_text, revive, disconnect) for the center dialog.

    Death and disconnect notices share the same dialog window, so the frame template only
    says "a dialog is open"; the text read from it decides which one it is.
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
    lowered = text.lower()
    if any(phrase in lowered for phrase in spec.ignore_phrases):
        return None, False, False
    revive = any(phrase in lowered for phrase in spec.revive_phrases)
    disconnect = not revive and any(phrase in lowered for phrase in spec.disconnect_phrases)
    return text, revive, disconnect
