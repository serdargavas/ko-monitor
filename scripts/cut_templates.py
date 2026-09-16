"""Cuts the Genie header and item icon templates out of the committed sample frames.

Run once; the templates are committed. Re-run only if the server changes its icons.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
GENIE_HEADER = (2330, 0, 230, 60)  # roi the header template is cut from
ARROW_COL, MANA_COL, ITEM_ROW = 6, 5, 3
TEMPLATE_HEIGHT = 27  # top strip of a slot: excludes the stack count, which changes


def main() -> int:
    on = cv2.imread(str(ROOT / "samples/genie_on/20260916-153935.png"))
    if on is None:
        print("samples/genie_on frame missing", file=sys.stderr)
        return 1
    out = ROOT / "templates"
    x, y, w, h = GENIE_HEADER
    cv2.imwrite(str(out / "genie_header.png"), on[y : y + h, x : x + w])

    inv = json.loads((ROOT / "calibration.json").read_text(encoding="utf-8"))["inventory"]
    ox, oy = inv["slot_origin"]
    sx, sy = inv["slot_step"]
    sw, _ = inv["slot_size"]
    for name, col in (("item_arrow", ARROW_COL), ("item_mana", MANA_COL)):
        cx, cy = ox + col * sx, oy + ITEM_ROW * sy
        cv2.imwrite(str(out / f"{name}.png"), on[cy : cy + TEMPLATE_HEIGHT, cx : cx + sw])
    print("templates written to", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
