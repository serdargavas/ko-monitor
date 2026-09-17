from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class State(StrEnum):
    CLOSED = "closed"
    ALIVE = "alive"
    DEAD = "dead"
    DISCONNECTED = "disconnected"
    FROZEN = "frozen"
    BLIND = "blind"


class CaptureStatus(StrEnum):
    OK = "ok"
    MINIMIZED = "minimized"
    NOT_FOUND = "not_found"
    BLACK = "black"
    NO_DISPLAY = "no_display"


class EventKind(StrEnum):
    GAME_STARTED = "game_started"
    GAME_CLOSED = "game_closed"
    DEAD = "dead"
    DISCONNECTED = "disconnected"
    FROZEN = "frozen"
    BLIND = "blind"
    RECOVERED = "recovered"
    INVENTORY_FULL = "inventory_full"
    ARROW_LOW = "arrow_low"
    MANA_LOW = "mana_low"
    TEST = "test"  # manual test notification from the PWA; never produced by the monitor


@dataclass
class Readings:
    """What the detectors saw on one frame. None means 'could not tell'."""

    hud_visible: bool = False
    hp: int | None = None
    hp_max: int | None = None
    zone: str | None = None
    revive_dialog: bool | None = None
    login_screen: bool | None = None
    disconnect_dialog: bool | None = None
    dialog_text: str | None = None  # text of the open center dialog; None = no dialog / not calibrated
    chat_events: list[str] = field(default_factory=list)
    inventory_open: bool | None = None
    money: int | None = None
    slots_used: int | None = None
    slots_total: int | None = None
    arrow_count: int | None = None
    arrow_unlimited: bool = False  # the never-emptying quiver is in the bag: nothing to count
    mana_count: int | None = None
    genie_active: bool | None = None  # None = the Genie panel could not be read
    frame_diff: float | None = None


@dataclass(frozen=True)
class Event:
    kind: EventKind
    ts: float
    detail: str = ""
    notify: bool = False


@dataclass(frozen=True)
class Snapshot:
    ts: float
    state: State
    hp: int | None
    hp_max: int | None
    zone: str | None
    money_last: int | None
    slots_used_last: int | None
    slots_total_last: int | None
    inventory_seen_at: float | None
