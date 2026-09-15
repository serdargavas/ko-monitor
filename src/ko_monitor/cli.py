from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2

from ko_monitor.capture import WgcCapture
from ko_monitor.config import Config, load_config


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args, load_config(args.config))
