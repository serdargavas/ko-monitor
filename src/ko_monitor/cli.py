from __future__ import annotations

import argparse
import dataclasses
import json
import time
from datetime import datetime
from pathlib import Path

import cv2

from ko_monitor.calibration import crop, load_calibration
from ko_monitor.capture import WgcCapture
from ko_monitor.config import Config, load_config


def parse_roi(text: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI must be x,y,w,h")
    return tuple(int(p) for p in parts)


def _read_image(path: Path):
    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"Görüntü okunamadı: {path}")
    return image


def _grab_one(cap: WgcCapture, timeout_s: float = 5.0):
    deadline = time.monotonic() + timeout_s
    status, frame = cap.latest()
    while frame is None and time.monotonic() < deadline:
        time.sleep(0.2)
        status, frame = cap.latest()
    return status, frame


def cmd_snap(args: argparse.Namespace, cfg: Config) -> int:
    cap = WgcCapture(cfg.window_title)
    try:
        status, frame = _grab_one(cap)
    finally:
        cap.close()
    if frame is None:
        print(f"Kare alınamadı: {status}")
        return 1
    out = Path("samples") / args.label / f"{datetime.now():%Y%m%d-%H%M%S}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), frame)
    print(out)
    return 0


def cmd_record(args: argparse.Namespace, cfg: Config) -> int:
    out_dir = Path("samples") / "replay" / args.label
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = WgcCapture(cfg.window_title)
    saved = 0
    try:
        _grab_one(cap)
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            status, frame = cap.latest()
            if frame is not None:
                saved += 1
                cv2.imwrite(str(out_dir / f"{saved:04d}.png"), frame)
            time.sleep(args.interval)
    finally:
        cap.close()
    print(f"{saved} kare -> {out_dir}")
    return 0 if saved else 1


def cmd_ocr(args: argparse.Namespace, cfg: Config) -> int:
    from ko_monitor.ocr import Ocr

    image = _read_image(args.image)
    ox, oy = 0, 0
    if args.roi:
        ox, oy = args.roi[0], args.roi[1]
        image = crop(image, args.roi)
    for line in Ocr(min_score=0.0).read_block(image):
        x, y, w, h = line.box
        print(f"{line.score:.2f}  x={x + ox} y={y + oy} w={w} h={h}  {line.text}")
    return 0


def cmd_crop(args: argparse.Namespace, cfg: Config) -> int:
    part = crop(_read_image(args.image), args.roi)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.out), part)
    print(f"{args.out} ({part.shape[1]}x{part.shape[0]})")
    return 0


def cmd_detect(args: argparse.Namespace, cfg: Config) -> int:
    from ko_monitor.detectors import Detector
    from ko_monitor.ocr import Ocr

    calib = load_calibration(cfg.calibration_path)
    detector = Detector(calib, Ocr(calib.ocr_min_score))
    for path in args.images:
        readings = detector.detect(_read_image(path))
        payload = None if readings is None else dataclasses.asdict(readings)
        print(path, json.dumps(payload, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ko_monitor")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snap", help="save the current game frame to samples/<label>/")
    snap.add_argument("label")
    snap.set_defaults(func=cmd_snap)

    record = sub.add_parser("record", help="save frames to samples/replay/<label>/ for replay")
    record.add_argument("label")
    record.add_argument("--seconds", type=float, default=30.0)
    record.add_argument("--interval", type=float, default=2.0)
    record.set_defaults(func=cmd_record)

    ocr = sub.add_parser("ocr", help="print all text found in an image (full-frame coordinates)")
    ocr.add_argument("image", type=Path)
    ocr.add_argument("--roi", type=parse_roi)
    ocr.set_defaults(func=cmd_ocr)

    crop_cmd = sub.add_parser("crop", help="cut a region out of an image (for templates)")
    crop_cmd.add_argument("image", type=Path)
    crop_cmd.add_argument("--roi", type=parse_roi, required=True)
    crop_cmd.add_argument("--out", type=Path, required=True)
    crop_cmd.set_defaults(func=cmd_crop)

    detect = sub.add_parser("detect", help="print Readings for images using calibration.json")
    detect.add_argument("images", type=Path, nargs="+")
    detect.set_defaults(func=cmd_detect)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args, load_config(args.config))
