from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Thresholds:
    tick_s: float = 2.0
    closed_poll_s: float = 10.0
    snapshot_s: float = 60.0
    confirm_reads: int = 2
    disconnect_soft_s: float = 15.0
    frozen_s: float = 120.0
    blind_s: float = 60.0
    inventory_full_repeat_s: float = 600.0
    frozen_diff_max: float = 0.5
    snapshot_retention_s: float = 30 * 86400


@dataclass(frozen=True)
class PushConfig:
    contact: str = "mailto:you@example.com"
    max_age_s: float = 300.0


@dataclass(frozen=True)
class HeartbeatConfig:
    ping_url: str = ""
    api_key: str = ""


@dataclass(frozen=True)
class Config:
    process_name: str = "Client.acme"
    window_title: str = "Knight Evolution"
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    calibration_path: Path = Path("calibration.json")
    thresholds: Thresholds = field(default_factory=Thresholds)
    push: PushConfig = field(default_factory=PushConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)


def load_config(path: Path | None) -> Config:
    if path is None or not path.exists():
        return Config()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    general = raw.get("general", {})
    defaults = Config()
    return Config(
        process_name=general.get("process_name", defaults.process_name),
        window_title=general.get("window_title", defaults.window_title),
        data_dir=Path(general.get("data_dir", defaults.data_dir)),
        log_dir=Path(general.get("log_dir", defaults.log_dir)),
        calibration_path=Path(general.get("calibration_path", defaults.calibration_path)),
        thresholds=Thresholds(**raw.get("thresholds", {})),
        push=PushConfig(**raw.get("push", {})),
        heartbeat=HeartbeatConfig(**raw.get("heartbeat", {})),
    )
