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
class DialogSpec:
    """Center dialog shared by the death and disconnect notices; its text tells them apart."""

    frame: TemplateSpec
    text_rois: tuple[Roi, ...]
    revive_phrases: list[str]
    disconnect_phrases: list[str]
    ignore_phrases: list[str]


@dataclass(frozen=True)
class GenieSpec:
    """Knight Genie panel: the stop button is gold while it runs and grey while it is stopped."""

    header: TemplateSpec
    header_at: tuple[int, int]  # where the header template was cut from; boxes are relative to it
    stop_box: Roi
    play_box: Roi
    margin: float


@dataclass(frozen=True)
class ItemsSpec:
    arrow_file: Path
    mana_file: Path
    # The server sells a quiver that never empties; it shows as a stack of 1 and must not be
    # counted or alerted on. None = this account has never had one.
    arrow_unlimited_file: Path | None
    # Scrolls come in several colours with the same shape; one template per colour, because a
    # single template scores only 0.64 against the gold one.
    scroll_files: tuple[Path, ...]
    # Scrolls are matched colour-blind, so one shape covers every colour the server sells - and
    # the ones it adds later. Measured over every committed frame: scrolls score 0.82-1.00 in
    # grayscale, everything else at most 0.66.
    scroll_threshold: float
    match_threshold: float
    count_box: Roi  # stack count, relative to the slot's top-left corner
    template_height: int


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
    dialog: DialogSpec | None = None
    genie: GenieSpec | None = None
    items: ItemsSpec | None = None


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

    def phrases(values: list[str]) -> list[str]:
        return [p.lower() for p in values]

    dlg = raw.get("dialog")
    dialog = None
    if dlg is not None:
        dialog = DialogSpec(
            frame=template(dlg["frame"]),
            text_rois=tuple(tuple(roi) for roi in dlg["text_rois"]),
            revive_phrases=phrases(dlg.get("revive_phrases", [])),
            disconnect_phrases=phrases(dlg.get("disconnect_phrases", [])),
            ignore_phrases=phrases(dlg.get("ignore_phrases", [])),
        )
    gen = raw.get("genie")
    genie = None
    if gen is not None:
        genie = GenieSpec(
            header=template(gen["header"]),
            header_at=tuple(gen["header_at"]),
            stop_box=tuple(gen["stop_box"]),
            play_box=tuple(gen["play_box"]),
            margin=float(gen.get("margin", 60.0)),
        )

    itm = raw.get("items")
    items = None
    if itm is not None:
        items = ItemsSpec(
            arrow_file=base / itm["arrow_file"],
            mana_file=base / itm["mana_file"],
            arrow_unlimited_file=(
                base / itm["arrow_unlimited_file"] if itm.get("arrow_unlimited_file") else None
            ),
            scroll_files=tuple(base / f for f in itm.get("scroll_files", [])),
            scroll_threshold=float(itm.get("scroll_threshold", 0.75)),
            match_threshold=float(itm.get("match_threshold", 0.85)),
            count_box=tuple(itm["count_box"]),
            template_height=int(itm.get("template_height", 27)),
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
        dialog=dialog,
        genie=genie,
        items=items,
    )


def crop(frame: np.ndarray, roi: Roi) -> np.ndarray:
    x, y, w, h = roi
    return frame[y : y + h, x : x + w]
