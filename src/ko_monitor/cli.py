from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import re
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

import cv2

from ko_monitor.calibration import crop, load_calibration
from ko_monitor.capture import WgcCapture
from ko_monitor.config import PROJECT_ROOT, Config, load_config

log = logging.getLogger(__name__)

_HC_PING_URL = re.compile(
    r"^https://hc-ping\.com/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/?$", re.IGNORECASE
)


def run_config_warnings(cfg: Config, config_path: Path) -> list[str]:
    """Settings that silently weaken live monitoring."""
    warnings = []
    if not config_path.exists():
        warnings.append(f"config file {config_path} not found; using defaults")
    if not cfg.heartbeat.ping_url:
        warnings.append("heartbeat.ping_url is empty; heartbeat disabled")
    elif cfg.heartbeat.api_key and not _HC_PING_URL.match(cfg.heartbeat.ping_url):
        warnings.append(
            "heartbeat.ping_url does not look like https://hc-ping.com/<uuid>; heartbeat pause will fail"
        )
    return warnings


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


def cmd_run(args: argparse.Namespace, cfg: Config) -> int:
    import threading

    from ko_monitor.agent import Agent, run_replay
    from ko_monitor.detectors import Detector
    from ko_monitor.heartbeat import Heartbeat
    from ko_monitor.logging_setup import setup_logging
    from ko_monitor.monitor import Monitor
    from ko_monitor.notifier import WebPushNotifier
    from ko_monitor.ocr import Ocr
    from ko_monitor.process_watch import is_process_running
    from ko_monitor.storage import Storage
    from ko_monitor.vapid import ensure_vapid_key

    setup_logging(cfg.log_dir)
    if not args.replay:
        for warning in run_config_warnings(cfg, args.config):
            log.warning(warning)
    calib = load_calibration(cfg.calibration_path)
    detector = Detector(calib, Ocr(calib.ocr_min_score))

    if args.replay:
        db_path = cfg.data_dir / "replay.sqlite3"
        db_path.unlink(missing_ok=True)
        storage = Storage(db_path)
        try:
            for event in run_replay(cfg, args.replay, detector, storage):
                print(f"{event['kind']:<15} {event['detail']}")
        finally:
            storage.close()
        return 0

    storage = Storage(cfg.data_dir / "ko_monitor.sqlite3")
    notifier = WebPushNotifier(
        storage, ensure_vapid_key(cfg.data_dir / "vapid_private.pem"),
        cfg.push.contact, cfg.push.max_age_s,
    )
    source = WgcCapture(cfg.window_title, calib.black_threshold)
    agent = Agent(
        cfg, storage, source, detector, Monitor(cfg.thresholds), notifier,
        Heartbeat(cfg.heartbeat.ping_url, cfg.heartbeat.api_key),
        lambda: is_process_running(cfg.process_name),
    )
    stop = threading.Event()
    try:
        agent.run(stop)
    except KeyboardInterrupt:
        stop.set()
    finally:
        source.close()
        storage.close()
    return 0


def cmd_vapid(args: argparse.Namespace, cfg: Config) -> int:
    from ko_monitor.vapid import application_server_key, ensure_vapid_key

    print(application_server_key(ensure_vapid_key(cfg.data_dir / "vapid_private.pem")))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ko_monitor")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.toml")
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

    run = sub.add_parser("run", help="run the monitor (live, or --replay a folder of frames)")
    run.add_argument("--replay", type=Path)
    run.set_defaults(func=cmd_run)

    vapid = sub.add_parser("vapid", help="create the VAPID key if needed and print the public key")
    vapid.set_defaults(func=cmd_vapid)
    return parser


def main(argv: list[str] | None = None) -> int:
    # OCR output can contain characters outside the Windows console's active code page
    # (e.g. cp1254); reconfigure to UTF-8 so `ocr`/`detect` never crash on them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config, PROJECT_ROOT)
    except (tomllib.TOMLDecodeError, TypeError, ValueError) as exc:
        detail = " ".join(str(exc).split())
        print(f"Ayar dosyası hatalı: {args.config}: {detail}", file=sys.stderr)
        return 2
    return args.func(args, cfg)
