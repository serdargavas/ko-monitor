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

_DETAIL_MAX = 120

# Alerts that only matter while the genie farms: when the user plays in person they see these
# themselves, and a phone that keeps buzzing during manual play gets ignored.
_SILENCED_WHEN_GENIE_OFF = {
    EventKind.DEAD,
    EventKind.INVENTORY_FULL,
    EventKind.ARROW_LOW,
    EventKind.MANA_LOW,
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
        self.arrow_last: int | None = None
        self.mana_last: int | None = None
        self.genie_active: bool | None = None
        self.inventory_seen_at: float | None = None
        self._last_inventory_alert: float | None = None
        self._last_item_alert: dict[EventKind, float] = {}
        # Debounce for the Genie panel: a single misread must not silence the death alert, nor
        # un-silence it. The state changes only after confirm_reads identical readings.
        self._genie_pending: bool | None = None
        self._genie_reads = 0
        # Startup grace: launcher/login/character select show no HUD, so bad states
        # are not evaluated until the HUD is first seen or startup_grace_s passes.
        self._started_at: float | None = None
        self._in_grace = False
        self._reset_conditions()

    def _reset_conditions(self) -> None:
        self.last_readings: Readings | None = None
        self._dialog_text_last: str | None = None
        # The current DISCONNECTED state was caused by the center dialog (disconnect text or
        # unknown text): leaving it needs the dialog closed and the HUD visible.
        self._disconnect_by_dialog = False
        self._clear_timers()

    def _clear_timers(self) -> None:
        self._blind_since: float | None = None
        self._hud_missing_since: float | None = None
        self._still_since: float | None = None
        self._unknown_dialog_since: float | None = None
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
            self._started_at = obs.ts
            self._in_grace = True

        readable = obs.capture == CaptureStatus.OK and obs.readings is not None
        if self._in_grace:
            hud_seen = readable and obs.readings.hud_visible
            if hud_seen or obs.ts - self._started_at >= self._t.startup_grace_s:
                # Grace is over: normal rules start from clean conditions at this moment.
                self._in_grace = False
                self._clear_timers()

        if readable:
            self._blind_since = None
            self._update(obs.ts, obs.readings)
            events.extend(self._inventory_events(obs.ts, obs.readings))
            events.extend(self._item_events(obs.ts, obs.readings))
        elif self._blind_since is None:
            self._blind_since = obs.ts
            # "Uninterrupted" timers must not bridge a blind gap. A timer whose state is
            # already current is kept: leaving that state needs a positive reading.
            if self.state != State.DISCONNECTED:
                self._hud_missing_since = None
            if not (self.state == State.DISCONNECTED and self._disconnect_by_dialog):
                self._unknown_dialog_since = None
            if self.state != State.FROZEN:
                self._still_since = None

        if self._in_grace:
            self._clear_timers()
            return events

        target, by_dialog = self._target_state(obs.ts)
        self._disconnect_by_dialog = by_dialog
        if target != self.state:
            previous = self.state
            self.state = target
            if target == State.ALIVE:
                events.append(Event(EventKind.RECOVERED, obs.ts, previous.value))
            else:
                detail = self.zone_last or ""
                if by_dialog and self._dialog_text_last is not None:
                    detail = self._dialog_text_last[:_DETAIL_MAX]
                events.append(Event(_BAD_EVENTS[target], obs.ts, detail, notify=self._notify(_BAD_EVENTS[target])))
        return events

    def _notify(self, kind: EventKind) -> bool:
        """Genie off silences farm alerts; 'unknown' never silences anything."""
        return not (self.genie_active is False and kind in _SILENCED_WHEN_GENIE_OFF)

    def _update(self, ts: float, r: Readings) -> None:
        self.last_readings = r
        if r.zone:
            self.zone_last = r.zone
        if r.dialog_text is not None:
            self._dialog_text_last = r.dialog_text

        if r.hp == 0 or r.revive_dialog:
            self._dead_reads += 1
        elif r.hp is not None and r.hp > 0:
            self._dead_reads = 0

        # While dead (hp == 0) a disconnect-dialog read is most likely the death dialog with a
        # nameplate leaking through; DEAD already covers it. A dialog-caused DISCONNECTED is
        # held through garbled reads by _target_state, so reads here stay strictly consecutive.
        if r.login_screen or (r.disconnect_dialog and r.hp != 0):
            self._disconnect_reads += 1
        elif r.hud_visible:
            self._disconnect_reads = 0

        if r.dialog_text is None or r.revive_dialog or r.disconnect_dialog or r.hp == 0:
            self._unknown_dialog_since = None
        elif r.hp is not None and r.hp > 0 and self._unknown_dialog_since is None:
            self._unknown_dialog_since = ts

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

        if r.genie_active is None:
            self._genie_pending, self._genie_reads = None, 0
        else:
            if r.genie_active == self._genie_pending:
                self._genie_reads += 1
            else:
                self._genie_pending, self._genie_reads = r.genie_active, 1
            if self._genie_reads >= self._t.confirm_reads:
                was_off = self.genie_active is False
                self.genie_active = r.genie_active
                if was_off and self.genie_active is True:
                    # Farming resumed: re-arm farm alerts. Otherwise a bag/count that stayed bad
                    # through the whole silenced stretch keeps its throttle from the silent alert
                    # and the first real alert after resuming can be swallowed for up to
                    # item_low_repeat_s / inventory_full_repeat_s.
                    self._last_item_alert.clear()
                    self._last_inventory_alert = None
        if r.arrow_count is not None:
            self.arrow_last = r.arrow_count
        if r.mana_count is not None:
            self.mana_last = r.mana_count

        if r.inventory_open:
            self.inventory_seen_at = ts
            if r.money is not None:
                self.money_last = r.money
            if r.slots_used is not None:
                self.slots_used_last = r.slots_used
                self.slots_total_last = r.slots_total

    def _item_events(self, ts: float, r: Readings) -> list[Event]:
        events = []
        for kind, count, limit in (
            (EventKind.ARROW_LOW, r.arrow_count, self._t.arrow_low),
            (EventKind.MANA_LOW, r.mana_count, self._t.mana_low),
        ):
            if count is None:
                continue
            if count >= limit:
                self._last_item_alert.pop(kind, None)  # refilled: the next drop alerts again
                continue
            last = self._last_item_alert.get(kind)
            if last is not None and ts - last < self._t.item_low_repeat_s:
                continue
            self._last_item_alert[kind] = ts
            events.append(Event(kind, ts, str(count), notify=self._notify(kind)))
        return events

    def _inventory_events(self, ts: float, r: Readings) -> list[Event]:
        full_by_slots = bool(r.inventory_open) and r.slots_used is not None and r.slots_used == r.slots_total
        if "inventory_full" not in r.chat_events and not full_by_slots:
            return []
        last = self._last_inventory_alert
        if last is not None and ts - last < self._t.inventory_full_repeat_s:
            return []
        self._last_inventory_alert = ts
        return [Event(EventKind.INVENTORY_FULL, ts, self.zone_last or "", notify=self._notify(EventKind.INVENTORY_FULL))]

    def _disconnect_cause(self, ts: float) -> str | None:
        """'dialog' (center dialog text), 'other' (login screen, template, HUD missing) or None."""
        t = self._t
        if self._unknown_dialog_since is not None and ts - self._unknown_dialog_since >= t.unknown_dialog_s:
            return "dialog"
        if self._disconnect_reads >= t.confirm_reads:
            r = self.last_readings
            by_text = r is not None and bool(r.disconnect_dialog) and r.dialog_text is not None
            return "dialog" if by_text else "other"
        if self._hud_missing_since is not None and ts - self._hud_missing_since >= t.disconnect_soft_s:
            return "other"
        return None

    def _dialog_closed(self) -> bool:
        r = self.last_readings
        if r is None or not r.hud_visible:
            return False
        if r.dialog_text is None:
            return True
        # The death dialog uses the same window: a confirmed revive dialog means the disconnect
        # (or unknown) dialog is gone. A single revive misread must not release the hold.
        return bool(r.revive_dialog) and self._dead_reads >= self._t.confirm_reads

    def _target_state(self, ts: float) -> tuple[State, bool]:
        """Returns (target state, whether a DISCONNECTED target is caused by the center dialog)."""
        t = self._t
        held_by_dialog = self.state == State.DISCONNECTED and self._disconnect_by_dialog
        if self._blind_since is not None:
            if ts - self._blind_since >= t.blind_s:
                return State.BLIND, False
            return self.state, held_by_dialog
        cause = self._disconnect_cause(ts)
        if cause is not None:
            return State.DISCONNECTED, cause == "dialog" or held_by_dialog
        if held_by_dialog and not self._dialog_closed():
            return State.DISCONNECTED, True
        if self._dead_reads >= t.confirm_reads:
            return State.DEAD, False
        if (
            self.state in (State.ALIVE, State.FROZEN)
            and self._still_since is not None
            and ts - self._still_since >= t.frozen_s
        ):
            return State.FROZEN, False
        return State.ALIVE, False

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
