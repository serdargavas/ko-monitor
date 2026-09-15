"""Generates the PWA icons in frontend/public/icons with OpenCV (npm run build copies them to web/icons).

Run from the project root: .venv\\Scripts\\python.exe scripts\\make_icons.py
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "frontend" / "public" / "icons"
SIZES = (180, 192, 512)
BACKGROUND = (21, 17, 15)  # BGR of #0f1115, the app background
RING = (111, 191, 63)  # BGR of #3fbf6f, the "alive" green
PULSE = (240, 234, 232)  # BGR of #e8eaf0, the text color


def render_icon(size: int) -> np.ndarray:
    """Opaque square icon (iOS ignores transparency): a green ring with a heartbeat line."""
    scale = 4  # draw large, then downsample for smooth edges
    big = size * scale
    image = np.full((big, big, 3), BACKGROUND, np.uint8)
    cv2.circle(image, (big // 2, big // 2), int(big * 0.36), RING, int(big * 0.06), cv2.LINE_AA)
    pulse = np.array(
        [[0.20, 0.52], [0.38, 0.52], [0.45, 0.33], [0.55, 0.70], [0.62, 0.52], [0.80, 0.52]]
    ) * big
    cv2.polylines(image, [pulse.astype(np.int32)], False, PULSE, int(big * 0.045), cv2.LINE_AA)
    return cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA)


def main(out_dir: Path = ICON_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for size in SIZES:
        path = out_dir / f"icon-{size}.png"
        if not cv2.imwrite(str(path), render_icon(size)):
            raise SystemExit(f"could not write {path}")
        written.append(path)
    return written


if __name__ == "__main__":
    for icon_path in main():
        print(icon_path)
