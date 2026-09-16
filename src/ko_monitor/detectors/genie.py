"""Is Knight Genie running?

The panel's stop button is gold while the genie farms and grey while it is stopped; the play
button mirrors it. Measured on live frames: stop saturation 194-234 running / 66 stopped, play
76 running / 171 stopped. Comparing the two boxes instead of using an absolute threshold keeps
the verdict stable if the screen's brightness or gamma changes.
"""

from __future__ import annotations

import cv2
import numpy as np

from ko_monitor.calibration import GenieSpec, Roi, crop
from ko_monitor.detectors.templates import load_template


def _saturation(frame: np.ndarray, roi: Roi) -> float | None:
    x, y, w, h = roi
    if x < 0 or y < 0 or y + h > frame.shape[0] or x + w > frame.shape[1]:
        return None
    patch = frame[y : y + h, x : x + w]
    if patch.size == 0:
        return None
    return float(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[:, :, 1].mean())


def _shift(roi: Roi, dx: int, dy: int) -> Roi:
    x, y, w, h = roi
    return (x + dx, y + dy, w, h)


def read_genie(frame: np.ndarray, spec: GenieSpec | None) -> bool | None:
    """True = running, False = stopped, None = cannot tell (no panel, no template, unclear)."""
    if spec is None:
        return None
    template = load_template(str(spec.header.file))
    if template is None:
        return None
    region = crop(frame, spec.header.roi)
    if region.shape[0] < template.shape[0] or region.shape[1] < template.shape[1]:
        return None
    scores = np.nan_to_num(cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED))
    _, best, _, loc = cv2.minMaxLoc(scores)
    if float(best) < spec.header.threshold:
        return None
    # Where the header sits now versus where it sat when the template was cut.
    dx = spec.header.roi[0] + loc[0] - spec.header_at[0]
    dy = spec.header.roi[1] + loc[1] - spec.header_at[1]
    stop = _saturation(frame, _shift(spec.stop_box, dx, dy))
    play = _saturation(frame, _shift(spec.play_box, dx, dy))
    if stop is None or play is None:
        return None
    if stop - play >= spec.margin:
        return True
    if play - stop >= spec.margin:
        return False
    return None
