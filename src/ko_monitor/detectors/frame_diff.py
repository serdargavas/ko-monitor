from __future__ import annotations

import cv2
import numpy as np


class FrameDiff:
    """Mean absolute difference (0-255) between consecutive frames, downscaled to 64x36 gray."""

    def __init__(self) -> None:
        self._prev: np.ndarray | None = None

    def update(self, frame: np.ndarray) -> float | None:
        small = cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        previous, self._prev = self._prev, gray
        if previous is None:
            return None
        return float(np.abs(gray - previous).mean())
