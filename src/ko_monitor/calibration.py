from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

Roi = tuple[int, int, int, int]  # x, y, w, h


@dataclass(frozen=True)
class TemplateSpec:
    roi: Roi
    file: Path
    threshold: float


@dataclass(frozen=True)
class InventorySpec:
    window: TemplateSpec
    money_roi: Roi
    slot_origin: tuple[int, int]
    slot_size: tuple[int, int]
    slot_step: tuple[int, int]
    cols: int
    rows: int
    empty_slot_file: Path
    empty_max_diff: float


@dataclass(frozen=True)
class Calibration:
    resolution: tuple[int, int]
    hp_roi: Roi
    zone_roi: Roi
    chat_roi: Roi
    black_threshold: float
    ocr_min_score: float
    chat_phrases: dict[str, list[str]]
    templates: dict[str, TemplateSpec]
    inventory: InventorySpec | None


def load_calibration(path: Path) -> Calibration:
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent

    def template(d: dict) -> TemplateSpec:
        return TemplateSpec(tuple(d["roi"]), base / d["file"], float(d["threshold"]))

    inv = raw.get("inventory")
    inventory = None
    if inv is not None:
        inventory = InventorySpec(
            window=template(inv["window"]),
            money_roi=tuple(inv["money_roi"]),
            slot_origin=tuple(inv["slot_origin"]),
            slot_size=tuple(inv["slot_size"]),
            slot_step=tuple(inv["slot_step"]),
            cols=int(inv["cols"]),
            rows=int(inv["rows"]),
            empty_slot_file=base / inv["empty_slot_file"],
            empty_max_diff=float(inv["empty_max_diff"]),
        )
    return Calibration(
        resolution=tuple(raw["resolution"]),
        hp_roi=tuple(raw["hp_roi"]),
        zone_roi=tuple(raw["zone_roi"]),
        chat_roi=tuple(raw["chat_roi"]),
        black_threshold=float(raw.get("black_threshold", 0.95)),
        ocr_min_score=float(raw.get("ocr_min_score", 0.8)),
        chat_phrases={k: [p.lower() for p in v] for k, v in raw.get("chat_phrases", {}).items()},
        templates={k: template(v) for k, v in raw.get("templates", {}).items()},
        inventory=inventory,
    )


def crop(frame: np.ndarray, roi: Roi) -> np.ndarray:
    x, y, w, h = roi
    return frame[y : y + h, x : x + w]
