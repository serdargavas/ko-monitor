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

# ... except that a stopped genie is not proof the user is at the keyboard: the bot also stops
# when it crashes, gets kicked or cannot act, and the classic AFK disaster is "bot stops ->
# character stands still -> character dies". Only DEAD is expensive enough to miss, so only DEAD
# waits out genie_off_grace_s; a redundant "bag full" buzz costs nothing.
_GRACE_BEFORE_SILENCE = {EventKind.DEAD}


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
        self.arrow_unlimited = False
        self.mana_last: int | None = None
        self.scrolls_last: int | None = None
        self.genie_active: bool | None = None
        self.inventory_seen_at: float | None = None
        self._last_inventory_alert: float | None = None
        self._last_item_alert: dict[EventKind, float] = {}
        # Consecutive below-threshold readings per item kind. read_items reports 0 whenever no
        # icon matches, which also happens when a trade/shop window covers the bag grid or the
        # user flipped to another bag page, and a clipped OCR read ("6380" -> "380") looks just
        # as low. One frame must not push; the debounce mirrors _dead_reads/_disconnect_reads.
        self._item_low_reads: dict[EventKind, int] = {}
        # Kinds _notify actually silenced (not merely throttled) while genie_active was False:
        # exactly the alerts the user never saw. Re-armed on resume; a kind that was pushed for
        # real during the off period is NOT in here and keeps its normal repeat window.
        self._silenced_while_off: set[EventKind] = set()
        # Debounce for the Genie panel: a single misread must not silence the death alert, nor
        # un-silence it. The state changes only after confirm_reads identical readings.
        self._genie_pending: bool | None = None
        self._genie_reads = 0
        # When genie_active last became a confirmed False. A user who sat down to play stopped
        # the bot minutes ago; a bot that stopped because of trouble stopped seconds ago.
        self._genie_off_since: float | None = None
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
                kind = _BAD_EVENTS[target]
                events.append(Event(kind, obs.ts, detail, notify=self._notify(kind, obs.ts)))
        return events

    def _notify(self, kind: EventKind, ts: float) -> bool:
        """Genie off silences farm alerts; 'unknown' never silences anything."""
        if self.genie_active is not False or kind not in _SILENCED_WHEN_GENIE_OFF:
            return True
        if kind in _GRACE_BEFORE_SILENCE:
            off_since = self._genie_off_since
            if off_since is None or ts - off_since < self._t.genie_off_grace_s:
                # The bot stopped moments ago: much more likely a crash/kick that killed the
                # character than a user who sat down to play. Tell the phone.
                return True
        self._silenced_while_off.add(kind)
        return False

    def _set_genie(self, ts: float, value: bool | None) -> None:
        """Applies a confirmed genie state and keeps the 'off since' clock and re-arming honest."""
        was_off = self.genie_active is False
        self.genie_active = value
        if value is False:
            if not was_off:
                self._genie_off_since = ts
            return
        self._genie_off_since = None
        if was_off:
            self._rearm_silenced()

    def _rearm_silenced(self) -> None:
        """Silencing ended: alerts the user never saw must be allowed to fire again.

        Only the kinds actually silenced while off are re-armed (the user never saw them) - not
        every kind, or a real push made just before an unrelated genie flap would lose its repeat
        window and get a spurious second push seconds later.
        """
        for kind in self._silenced_while_off:
            if kind == EventKind.INVENTORY_FULL:
                self._last_inventory_alert = None
            elif kind in (EventKind.ARROW_LOW, EventKind.MANA_LOW):
                self._last_item_alert.pop(kind, None)
            # EventKind.DEAD cannot be re-armed and is deliberately not handled here: it is a
            # state-transition event, the state is still DEAD, and nothing re-emits it. A death
            # silenced during an off period stays unreported for the rest of its life - which is
            # why _notify's grace window, not this loop, is what keeps a real death audible.
        self._silenced_while_off.clear()

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
            # An unreadable panel means "unknown", and unknown silences nothing (spec 2 and 9).
            # Keeping the last confirmed value here would silence the death alert forever once
            # the panel is closed, dragged out of the search band or covered by another window,
            # so unknown takes effect immediately - it is the safe direction. The streak resets
            # too: two fresh confirming reads are needed before silencing can come back.
            self._genie_pending, self._genie_reads = None, 0
            self._set_genie(ts, None)
        else:
            if r.genie_active == self._genie_pending:
                self._genie_reads += 1
            else:
                self._genie_pending, self._genie_reads = r.genie_active, 1
            if self._genie_reads >= self._t.confirm_reads:
                self._set_genie(ts, r.genie_active)
        self.arrow_unlimited = r.arrow_unlimited
        if r.arrow_count is not None:
            self.arrow_last = r.arrow_count
        if r.mana_count is not None:
            self.mana_last = r.mana_count
        if r.scroll_count is not None:
            self.scrolls_last = r.scroll_count

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
            # An unlimited quiver has no count worth watching: never alert on arrows while it is there.
            (EventKind.ARROW_LOW, None if r.arrow_unlimited else r.arrow_count, self._t.arrow_low),
            (EventKind.MANA_LOW, r.mana_count, self._t.mana_low),
        ):
            if count is None:
                continue  # bag closed: no evidence either way, the streak simply waits
            if count >= limit:
                self._item_low_reads[kind] = 0
                self._last_item_alert.pop(kind, None)  # refilled: the next drop alerts again
                continue
            self._item_low_reads[kind] = self._item_low_reads.get(kind, 0) + 1
            if self._item_low_reads[kind] < self._t.confirm_reads:
                continue  # one low frame can be an occluded bag grid or a clipped OCR read
            last = self._last_item_alert.get(kind)
            if last is not None and ts - last < self._t.item_low_repeat_s:
                continue
            self._last_item_alert[kind] = ts
            events.append(Event(kind, ts, str(count), notify=self._notify(kind, ts)))
        return events

    def _inventory_events(self, ts: float, r: Readings) -> list[Event]:
        full_by_slots = bool(r.inventory_open) and r.slots_used is not None and r.slots_used == r.slots_total
        if "inventory_full" not in r.chat_events and not full_by_slots:
            return []
        last = self._last_inventory_alert
        if last is not None and ts - last < self._t.inventory_full_repeat_s:
            return []
        self._last_inventory_alert = ts
        notify = self._notify(EventKind.INVENTORY_FULL, ts)
        return [Event(EventKind.INVENTORY_FULL, ts, self.zone_last or "", notify=notify)]

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
            scrolls_last=self.scrolls_last,
        )
