from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from ko_monitor.calibration import TemplateSpec, crop


@lru_cache(maxsize=64)
def load_template(path: str) -> np.ndarray | None:
    if not Path(path).exists():
        return None
    return cv2.imread(path)


def template_present(frame: np.ndarray, spec: TemplateSpec | None) -> bool | None:
    """None = not calibrated (no spec or template file yet)."""
    if spec is None:
        return None
    template = load_template(str(spec.file))
    if template is None:
        return None
    region = crop(frame, spec.roi)
    if region.shape[0] < template.shape[0] or region.shape[1] < template.shape[1]:
        return False
    scores = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    return float(np.nan_to_num(scores).max()) >= spec.threshold
