from __future__ import annotations

from dataclasses import dataclass

from ko_monitor.config import Thresholds
from ko_monitor.models import CaptureStatus, Event, EventKind, Readings, Snapshot, State

_BAD_EVENTS = {
    State.DEAD: EventKind.DEAD,
    State.DISCONNECTED: EventKind.DISCONNECTED,
    State.FROZEN: EventKind.FROZEN,
    State.BLIND: EventKind.BLIND,
}


@dataclass(frozen=True)
class Observation:
    ts: float
    process_running: bool
    capture: CaptureStatus | None = None
    readings: Readings | None = None


class Monitor:
    """Pure state machine: observations in, events out. No I/O, no clock."""

    def __init__(self, thresholds: Thresholds):
        self._t = thresholds
        self.state: State | None = None
        self.zone_last: str | None = None
        self.money_last: int | None = None
        self.slots_used_last: int | None = None
        self.slots_total_last: int | None = None
        self.inventory_seen_at: float | None = None
        self._last_inventory_alert: float | None = None
        self._reset_conditions()

    def _reset_conditions(self) -> None:
        self.last_readings: Readings | None = None
        self._blind_since: float | None = None
        self._hud_missing_since: float | None = None
        self._still_since: float | None = None
        self._dead_reads = 0
        self._disconnect_reads = 0

    def observe(self, obs: Observation) -> list[Event]:
        events: list[Event] = []
        if not obs.process_running:
            if self.state not in (None, State.CLOSED):
                events.append(Event(EventKind.GAME_CLOSED, obs.ts, notify=True))
            self._reset_conditions()
            self.state = State.CLOSED
            return events

        if self.state in (None, State.CLOSED):
            events.append(Event(EventKind.GAME_STARTED, obs.ts))
            self.state = State.ALIVE

        if obs.capture == CaptureStatus.OK and obs.readings is not None:
            self._blind_since = None
            self._update(obs.ts, obs.readings)
            events.extend(self._inventory_events(obs.ts, obs.readings))
        elif self._blind_since is None:
            self._blind_since = obs.ts

        target = self._target_state(obs.ts)
        if target != self.state:
            previous = self.state
            self.state = target
            if target == State.ALIVE:
                events.append(Event(EventKind.RECOVERED, obs.ts, previous.value))
            else:
                events.append(Event(_BAD_EVENTS[target], obs.ts, self.zone_last or "", notify=True))
        return events

    def _update(self, ts: float, r: Readings) -> None:
        self.last_readings = r
        if r.zone:
            self.zone_last = r.zone

        if r.hp == 0 or r.revive_dialog:
            self._dead_reads += 1
        elif r.hp is not None and r.hp > 0:
            self._dead_reads = 0

        if r.login_screen or r.disconnect_dialog:
            self._disconnect_reads += 1
        elif r.hud_visible:
            self._disconnect_reads = 0

        if r.hud_visible:
            self._hud_missing_since = None
        elif self._hud_missing_since is None:
            self._hud_missing_since = ts

        if r.frame_diff is not None:
            if r.frame_diff <= self._t.frozen_diff_max:
                if self._still_since is None:
                    self._still_since = ts
            else:
                self._still_since = None

        if r.inventory_open:
            self.inventory_seen_at = ts
            if r.money is not None:
                self.money_last = r.money
            if r.slots_used is not None:
                self.slots_used_last = r.slots_used
                self.slots_total_last = r.slots_total

    def _inventory_events(self, ts: float, r: Readings) -> list[Event]:
        full_by_slots = bool(r.inventory_open) and r.slots_used is not None and r.slots_used == r.slots_total
        if "inventory_full" not in r.chat_events and not full_by_slots:
            return []
        last = self._last_inventory_alert
        if last is not None and ts - last < self._t.inventory_full_repeat_s:
            return []
        self._last_inventory_alert = ts
        return [Event(EventKind.INVENTORY_FULL, ts, self.zone_last or "", notify=True)]

    def _target_state(self, ts: float) -> State:
        t = self._t
        if self._blind_since is not None:
            return State.BLIND if ts - self._blind_since >= t.blind_s else self.state
        if self._disconnect_reads >= t.confirm_reads:
            return State.DISCONNECTED
        if self._hud_missing_since is not None and ts - self._hud_missing_since >= t.disconnect_soft_s:
            return State.DISCONNECTED
        if self._dead_reads >= t.confirm_reads:
            return State.DEAD
        if (
            self.state in (State.ALIVE, State.FROZEN)
            and self._still_since is not None
            and ts - self._still_since >= t.frozen_s
        ):
            return State.FROZEN
        return State.ALIVE

    def snapshot(self, ts: float) -> Snapshot:
        r = self.last_readings
        return Snapshot(
            ts=ts,
            state=self.state or State.CLOSED,
            hp=r.hp if r else None,
            hp_max=r.hp_max if r else None,
            zone=self.zone_last,
            money_last=self.money_last,
            slots_used_last=self.slots_used_last,
            slots_total_last=self.slots_total_last,
            inventory_seen_at=self.inventory_seen_at,
        )
