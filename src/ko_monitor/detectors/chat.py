from __future__ import annotations

import numpy as np

from ko_monitor.calibration import Calibration, crop
from ko_monitor.ocr import Ocr


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


class ChatTracker:
    """Finds lines added since the previous read. Chat scrolls up: new lines appear at the bottom."""

    def __init__(self) -> None:
        self._prev: list[str] | None = None

    def new_lines(self, lines: list[str]) -> list[str]:
        current = [normalize(line) for line in lines]
        previous, self._prev = self._prev, current
        if previous is None:
            return []
        for k in range(min(len(previous), len(current)), 0, -1):
            if previous[-k:] == current[:k]:
                return current[k:]
        seen = set(previous)
        return [line for line in current if line not in seen]


def classify(lines: list[str], phrases: dict[str, list[str]]) -> list[str]:
    found: list[str] = []
    for line in lines:
        for kind, patterns in phrases.items():
            if kind not in found and any(p in line for p in patterns):
                found.append(kind)
    return found


def read_chat(frame: np.ndarray, calib: Calibration, ocr: Ocr, tracker: ChatTracker) -> list[str]:
    lines = [line.text for line in ocr.read_block(crop(frame, calib.chat_roi))]
    return classify(tracker.new_lines(lines), calib.chat_phrases)
