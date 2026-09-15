import pytest

from ko_monitor.config import Thresholds
from ko_monitor.models import CaptureStatus, EventKind, Readings, State
from ko_monitor.monitor import Monitor, Observation

T = Thresholds()


def readings(**overrides) -> Readings:
    base = dict(hud_visible=True, hp=9000, hp_max=9996, zone="Ronark Land", frame_diff=5.0)
    base.update(overrides)
    return Readings(**base)


def ok(ts: float, **overrides) -> Observation:
    return Observation(ts, True, CaptureStatus.OK, readings(**overrides))


NO_HUD = dict(hud_visible=False, hp=None, hp_max=None, zone=None)


def kinds(events):
    return [(e.kind, e.notify) for e in events]


@pytest.fixture
def m() -> Monitor:
    monitor = Monitor(T)
    monitor.observe(ok(0.0))
    return monitor


def test_closed_at_start_is_silent():
    monitor = Monitor(T)
    assert monitor.observe(Observation(0.0, False)) == []
    assert monitor.state == State.CLOSED


def test_game_start_is_logged_not_notified():
    monitor = Monitor(T)
    assert kinds(monitor.observe(ok(0.0))) == [(EventKind.GAME_STARTED, False)]
    assert monitor.state == State.ALIVE


def test_death_needs_two_reads_and_notifies_once(m):
    assert m.observe(ok(2, hp=0)) == []
    events = m.observe(ok(4, hp=0))
    assert kinds(events) == [(EventKind.DEAD, True)]
    assert events[0].detail == "Ronark Land"
    assert m.observe(ok(6, hp=0)) == []
    assert m.state == State.DEAD


def test_revive_dialog_counts_as_death(m):
    m.observe(ok(2, revive_dialog=True))
    assert kinds(m.observe(ok(4, revive_dialog=True))) == [(EventKind.DEAD, True)]


def test_unreadable_hp_does_not_recover(m):
    m.observe(ok(2, hp=0))
    m.observe(ok(4, hp=0))
    assert m.observe(ok(6, **NO_HUD)) == []
    assert m.state == State.DEAD
    events = m.observe(ok(8, hp=5000))
    assert kinds(events) == [(EventKind.RECOVERED, False)]
    assert events[0].detail == "dead"


def test_explicit_disconnect(m):
    assert m.observe(ok(2, **NO_HUD, login_screen=True)) == []
    assert kinds(m.observe(ok(4, **NO_HUD, login_screen=True))) == [(EventKind.DISCONNECTED, True)]


def test_hud_missing_means_disconnect_after_15s(m):
    assert m.observe(ok(2, **NO_HUD)) == []
    assert m.observe(ok(16, **NO_HUD)) == []
    assert kinds(m.observe(ok(17, **NO_HUD))) == [(EventKind.DISCONNECTED, True)]
    assert kinds(m.observe(ok(19))) == [(EventKind.RECOVERED, False)]


def test_frozen_after_120s_and_recovers_on_change(m):
    assert m.observe(ok(2, frame_diff=0.0)) == []
    assert m.observe(ok(121, frame_diff=0.0)) == []
    assert kinds(m.observe(ok(122, frame_diff=0.0))) == [(EventKind.FROZEN, True)]
    assert kinds(m.observe(ok(124, frame_diff=3.0))) == [(EventKind.RECOVERED, False)]


def test_frozen_not_reported_while_dead(m):
    m.observe(ok(2, hp=0, frame_diff=0.0))
    m.observe(ok(4, hp=0, frame_diff=0.0))
    assert m.observe(ok(200, hp=0, frame_diff=0.0)) == []
    assert m.state == State.DEAD


def test_blind_after_60s_then_recovers(m):
    assert m.observe(Observation(2, True, CaptureStatus.MINIMIZED)) == []
    assert m.observe(Observation(61, True, CaptureStatus.MINIMIZED)) == []
    assert kinds(m.observe(Observation(62, True, CaptureStatus.MINIMIZED))) == [(EventKind.BLIND, True)]
    assert kinds(m.observe(ok(64))) == [(EventKind.RECOVERED, False)]


def test_short_blind_during_death_does_not_renotify(m):
    m.observe(ok(2, hp=0))
    m.observe(ok(4, hp=0))
    assert m.observe(Observation(6, True, CaptureStatus.MINIMIZED)) == []
    assert m.observe(Observation(30, True, CaptureStatus.BLACK)) == []
    assert m.state == State.DEAD
    assert m.observe(ok(32, hp=0)) == []
    assert m.state == State.DEAD


def test_unreadable_frame_counts_as_blind(m):
    assert m.observe(Observation(2, True, CaptureStatus.OK, None)) == []
    assert kinds(m.observe(Observation(62, True, CaptureStatus.OK, None))) == [(EventKind.BLIND, True)]


def test_disconnect_outranks_death(m):
    m.observe(ok(2, hp=0, login_screen=True))
    assert kinds(m.observe(ok(4, hp=0, login_screen=True))) == [(EventKind.DISCONNECTED, True)]


def test_death_then_disconnect_notifies_again(m):
    m.observe(ok(2, hp=0))
    m.observe(ok(4, hp=0))
    assert m.observe(ok(6, **NO_HUD, disconnect_dialog=True)) == []
    assert kinds(m.observe(ok(8, **NO_HUD, disconnect_dialog=True))) == [(EventKind.DISCONNECTED, True)]


def test_game_closed_while_monitoring(m):
    assert kinds(m.observe(Observation(10, False))) == [(EventKind.GAME_CLOSED, True)]
    assert m.observe(Observation(20, False)) == []
    assert kinds(m.observe(ok(30))) == [(EventKind.GAME_STARTED, False)]


def test_inventory_full_from_chat_is_throttled(m):
    assert kinds(m.observe(ok(2, chat_events=["inventory_full"]))) == [(EventKind.INVENTORY_FULL, True)]
    assert m.observe(ok(100, chat_events=["inventory_full"])) == []
    assert kinds(m.observe(ok(602, chat_events=["inventory_full"]))) == [(EventKind.INVENTORY_FULL, True)]


def test_inventory_full_from_slots_and_snapshot_keeps_last_seen(m):
    events = m.observe(ok(2, inventory_open=True, money=1_500_000, slots_used=28, slots_total=28))
    assert kinds(events) == [(EventKind.INVENTORY_FULL, True)]
    m.observe(ok(4))
    snap = m.snapshot(5)
    assert (snap.state, snap.hp, snap.hp_max, snap.zone) == (State.ALIVE, 9000, 9996, "Ronark Land")
    assert (snap.money_last, snap.slots_used_last, snap.slots_total_last) == (1_500_000, 28, 28)
    assert snap.inventory_seen_at == 2


def test_snapshot_when_closed():
    monitor = Monitor(T)
    monitor.observe(Observation(0, False))
    snap = monitor.snapshot(1)
    assert (snap.state, snap.hp) == (State.CLOSED, None)
