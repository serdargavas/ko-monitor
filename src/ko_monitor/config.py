from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

STREAM_QUALITIES = ("low", "medium", "high")


@dataclass(frozen=True)
class Thresholds:
    tick_s: float = 2.0
    closed_poll_s: float = 10.0
    snapshot_s: float = 60.0
    confirm_reads: int = 2
    disconnect_soft_s: float = 15.0
    frozen_s: float = 120.0
    blind_s: float = 60.0
    startup_grace_s: float = 300.0
    unknown_dialog_s: float = 30.0
    inventory_full_repeat_s: float = 600.0
    arrow_low: int = 1000
    mana_low: int = 200
    item_low_repeat_s: float = 600.0
    genie_off_grace_s: float = 120.0
    income_max_jump: int = 50_000_000
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
class ApiConfig:
    port: int = 8765
    stream_quality: str = "medium"  # used when a stream client does not ask for a quality

    def __post_init__(self) -> None:
        if not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ValueError(f"api.port must be an integer between 1 and 65535, got {self.port!r}")
        if self.stream_quality not in STREAM_QUALITIES:
            raise ValueError(
                f"api.stream_quality must be one of {', '.join(STREAM_QUALITIES)}, got {self.stream_quality!r}"
            )


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
    api: ApiConfig = field(default_factory=ApiConfig)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: Path | None, base_dir: Path = PROJECT_ROOT) -> Config:
    """Relative paths resolve against the config file's folder, or base_dir when there is no file.

    Raises tomllib.TOMLDecodeError for invalid TOML, TypeError for unknown keys in a section
    and ValueError for invalid [api] values.
    """
    if path is not None and path.exists():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        base = path.resolve().parent
    else:
        raw = {}
        base = base_dir

    def resolve(value: str | Path) -> Path:
        p = Path(value)
        return p if p.is_absolute() else base / p

    general = raw.get("general", {})
    defaults = Config()
    return Config(
        process_name=general.get("process_name", defaults.process_name),
        window_title=general.get("window_title", defaults.window_title),
        data_dir=resolve(general.get("data_dir", defaults.data_dir)),
        log_dir=resolve(general.get("log_dir", defaults.log_dir)),
        calibration_path=resolve(general.get("calibration_path", defaults.calibration_path)),
        thresholds=Thresholds(**raw.get("thresholds", {})),
        push=PushConfig(**raw.get("push", {})),
        heartbeat=HeartbeatConfig(**raw.get("heartbeat", {})),
        api=ApiConfig(**raw.get("api", {})),
    )
