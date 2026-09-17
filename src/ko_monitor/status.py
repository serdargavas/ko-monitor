"""Immutable agent status shared between the agent loop thread and the API thread."""

from __future__ import annotations

import dataclasses
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ko_monitor.models import CaptureStatus

if TYPE_CHECKING:
    from ko_monitor.monitor import Monitor


@dataclass(frozen=True)
class AgentStatus:
    """What the agent knew after one tick. Built from copies, so other threads can read it freely."""

    updated_at: float | None = None
    state: str | None = None
    process_running: bool = False
    capture: str | None = None
    readings: dict | None = None
    zone_last: str | None = None
    money_last: int | None = None
    slots_used_last: int | None = None
    slots_total_last: int | None = None
    arrow_last: int | None = None
    arrow_unlimited: bool = False
    mana_last: int | None = None
    scrolls_last: int | None = None
    genie_active: bool | None = None
    inventory_seen_at: float | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _plain(value):
    """Deep-copies into JSON-friendly Python values (numpy scalars from detectors become int/float)."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, bytes, bool, int, float)) or value is None:
        return value
    if hasattr(value, "item"):
        return value.item()
    return value


def status_from(
    monitor: Monitor, ts: float, process_running: bool, capture: CaptureStatus | None
) -> AgentStatus:
    readings = monitor.last_readings
    return AgentStatus(
        updated_at=ts,
        state=monitor.state.value if monitor.state is not None else None,
        process_running=process_running,
        capture=capture.value if capture is not None else None,
        # asdict() is generic: fields added to Readings later are published without changes here.
        readings=_plain(dataclasses.asdict(readings)) if readings is not None else None,
        zone_last=monitor.zone_last,
        money_last=_plain(monitor.money_last),
        slots_used_last=_plain(monitor.slots_used_last),
        slots_total_last=_plain(monitor.slots_total_last),
        arrow_last=_plain(monitor.arrow_last),
        arrow_unlimited=monitor.arrow_unlimited,
        mana_last=_plain(monitor.mana_last),
        scrolls_last=_plain(monitor.scrolls_last),
        genie_active=_plain(monitor.genie_active),
        inventory_seen_at=monitor.inventory_seen_at,
    )


class StatusBoard:
    """The agent loop publishes, the API reads. Statuses are immutable; the lock guards the swap."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = AgentStatus()

    def publish(self, status: AgentStatus) -> None:
        with self._lock:
            self._status = status

    def current(self) -> AgentStatus:
        with self._lock:
            return self._status
