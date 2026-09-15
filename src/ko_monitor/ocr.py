from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ko_monitor.calibration import Roi


@dataclass(frozen=True)
class OcrLine:
    text: str
    score: float
    box: Roi


class Ocr:
    """RapidOCR wrapper. Not thread-safe: use from the agent loop thread only."""

    def __init__(self, min_score: float = 0.8):
        from rapidocr import RapidOCR

        # onnxruntime uses every core by default; cap it so OCR does not starve the game.
        self._engine = RapidOCR(
            params={
                "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
        )
        self._min_score = min_score

    def read_line(self, image: np.ndarray) -> tuple[str, float] | None:
        """Recognition only (~15 ms). The image must contain a single line of text."""
        result = self._engine(image, use_det=False, use_cls=False, use_rec=True)
        if not result.txts:
            return None
        text, score = result.txts[0], float(result.scores[0])
        return (text, score) if score >= self._min_score else None

    def read_block(self, image: np.ndarray) -> list[OcrLine]:
        """Detection + recognition (~0.8 s for the chat area). Lines sorted top to bottom."""
        result = self._engine(image, use_det=True, use_cls=False, use_rec=True)
        if result.txts is None or result.boxes is None:
            return []
        lines = []
        for box, text, score in zip(result.boxes, result.txts, result.scores):
            if float(score) < self._min_score:
                continue
            xs = [int(p[0]) for p in box]
            ys = [int(p[1]) for p in box]
            lines.append(
                OcrLine(text, float(score), (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
            )
        lines.sort(key=lambda line: line.box[1])
        return lines
