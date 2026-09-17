from datetime import datetime

from ko_monitor.income import daily_income, day_starts, hourly_income
from ko_monitor.models import Snapshot, State

HOUR = 3600.0


def snap(ts: float, money: int | None) -> Snapshot:
    return Snapshot(ts, State.ALIVE, 100, 100, "Ronark Land", money, 10, 28, ts)


def test_empty_history():
    out = hourly_income([], now=HOUR * 10, hours=3)
    assert [h["delta"] for h in out["hours"]] == [None, None, None]
    assert out["avg_1h"] is None and out["avg_24h"] is None


def test_one_hour_delta_is_last_minus_first():
    snaps = [snap(HOUR * 9 + 60, 1000), snap(HOUR * 9 + 1800, 1500), snap(HOUR * 9 + 3000, 2200)]
    out = hourly_income(snaps, now=HOUR * 9 + 3500, hours=1)
    assert out["hours"][0]["delta"] == 1200
    assert out["hours"][0]["samples"] == 3
    assert out["hours"][0]["start"] == HOUR * 9


def test_hours_without_data_are_null_and_excluded_from_the_average():
    snaps = [snap(HOUR * 10 + 60, 1000), snap(HOUR * 10 + 3000, 3000)]
    out = hourly_income(snaps, now=HOUR * 12 + 10, hours=3)
    deltas = [h["delta"] for h in out["hours"]]
    assert deltas == [2000, None, None]
    assert out["avg_24h"] == 2000  # the two empty hours do not drag the average down


def test_a_single_ocr_glitch_is_skipped():
    # 1000 -> 999999999 -> 2000: the middle reading is impossible, so both steps around it drop.
    snaps = [snap(HOUR * 9 + 10, 1000), snap(HOUR * 9 + 20, 999_999_999), snap(HOUR * 9 + 30, 2000)]
    out = hourly_income(snaps, now=HOUR * 9 + 40, hours=1, max_jump=50_000_000)
    assert out["hours"][0]["delta"] == 0


def test_spending_shows_as_negative():
    snaps = [snap(HOUR * 9 + 10, 5000), snap(HOUR * 9 + 20, 3000)]
    out = hourly_income(snaps, now=HOUR * 9 + 40, hours=1)
    assert out["hours"][0]["delta"] == -2000


def test_null_money_readings_are_ignored():
    snaps = [snap(HOUR * 9 + 10, None), snap(HOUR * 9 + 20, 1000), snap(HOUR * 9 + 30, 1400)]
    out = hourly_income(snaps, now=HOUR * 9 + 40, hours=1)
    assert out["hours"][0]["delta"] == 400
    assert out["hours"][0]["samples"] == 2


def stale(ts: float, money: int, seen_at: float) -> Snapshot:
    """A snapshot written with the bag closed: money_last is whatever was last read at seen_at."""
    return Snapshot(ts, State.ALIVE, 100, 100, "Ronark Land", money, 10, 28, seen_at)


def test_hour_with_only_stale_money_has_no_data():
    # The bag was last seen in hour 9; hour 10 is 60 snapshots repeating that same number. That
    # is "no data", not "earned nothing" - reporting 0 would drag the averages down.
    snaps = [stale(HOUR * 10 + 60 * i, 5000, HOUR * 9 + 3000) for i in range(60)]
    out = hourly_income(snaps, now=HOUR * 10 + 3599, hours=1)
    assert out["hours"][0] == {"start": HOUR * 10, "delta": None, "samples": 0}
    assert out["avg_1h"] is None


def test_mixed_hour_counts_only_the_fresh_readings():
    # Bag shut for the first ten minutes of the hour (money_last still repeating hour 10's last
    # reading), then open for three minutes, then shut again (repeating the 1800 it just read).
    before = [stale(HOUR * 11 + 60 * i, 900, HOUR * 10 + 3000) for i in range(10)]
    fresh = [snap(HOUR * 11 + 660, 1000), snap(HOUR * 11 + 720, 1500), snap(HOUR * 11 + 780, 1800)]
    after = [stale(HOUR * 11 + 840 + 60 * i, 1800, HOUR * 11 + 780) for i in range(10)]
    out = hourly_income(before + fresh + after, now=HOUR * 11 + 3000, hours=1)
    assert out["hours"][0]["samples"] == 3
    assert out["hours"][0]["delta"] == 800


def test_inventory_seen_in_an_earlier_hour_does_not_count():
    # One fresh reading is not enough for a delta: an hour needs two readings of its own.
    snaps = [stale(HOUR * 12 + 10, 900, HOUR * 11 + 10), snap(HOUR * 12 + 20, 1000)]
    out = hourly_income(snaps, now=HOUR * 12 + 30, hours=1)
    assert out["hours"][0] == {"start": HOUR * 12, "delta": None, "samples": 1}


def local(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> float:
    return datetime(year, month, day, hour, minute).timestamp()


def test_day_starts_are_local_midnights():
    starts = day_starts(local(2026, 9, 16, 10, 30), days=3)
    moments = [datetime.fromtimestamp(s) for s in starts]
    assert [m.day for m in moments] == [14, 15, 16]
    assert all((m.hour, m.minute, m.second) == (0, 0, 0) for m in moments)


def test_a_day_runs_from_local_midnight_not_from_a_86400_boundary():
    # Bucketing by 86400 s would put this user's boundary at 03:00 and split a night's farming.
    snaps = [
        snap(local(2026, 9, 15, 23, 0), 1000),
        snap(local(2026, 9, 15, 23, 30), 1500),
        snap(local(2026, 9, 16, 0, 10), 4000),
        snap(local(2026, 9, 16, 1, 0), 4700),
    ]
    out = daily_income(snaps, now=local(2026, 9, 16, 2, 0), days=2)
    assert [d["delta"] for d in out["days"]] == [500, 700]
    assert out["days"][1]["start"] == local(2026, 9, 16)


def test_the_running_day_is_left_out_of_the_averages():
    # Today is two hours old; counting it would drag the daily average down every morning.
    snaps = [
        snap(local(2026, 9, 14, 12, 0), 0),
        snap(local(2026, 9, 14, 20, 0), 10_000),
        snap(local(2026, 9, 15, 12, 0), 0),
        snap(local(2026, 9, 15, 20, 0), 20_000),
        snap(local(2026, 9, 16, 1, 0), 0),
        snap(local(2026, 9, 16, 1, 30), 500),
    ]
    out = daily_income(snaps, now=local(2026, 9, 16, 2, 0), days=3)
    assert [d["delta"] for d in out["days"]] == [10_000, 20_000, 500]
    assert out["avg_all"] == 15_000
    assert out["avg_7d"] == 15_000


def test_a_day_without_readings_is_null():
    snaps = [snap(local(2026, 9, 16, 1, 0), 100), snap(local(2026, 9, 16, 1, 30), 900)]
    out = daily_income(snaps, now=local(2026, 9, 16, 2, 0), days=3)
    assert [d["delta"] for d in out["days"]] == [None, None, 800]
    assert out["avg_all"] is None  # only the running day had data, and it does not count


def test_daily_income_ignores_stale_money_readings():
    fresh = Snapshot(local(2026, 9, 15, 12, 0), State.ALIVE, 1, 1, "z", 1000, 1, 28, local(2026, 9, 15, 12, 0))
    stale = Snapshot(local(2026, 9, 15, 18, 0), State.ALIVE, 1, 1, "z", 1000, 1, 28, local(2026, 9, 14, 23, 0))
    out = daily_income([fresh, stale], now=local(2026, 9, 15, 20, 0), days=1)
    assert out["days"][0]["samples"] == 1
    assert out["days"][0]["delta"] is None


def scroll_snap(ts: float, money: int, scrolls: int | None) -> Snapshot:
    return Snapshot(ts, State.ALIVE, 100, 100, "Ronark Land", money, 10, 28, ts, scrolls)


def test_scrolls_in_the_bag_count_as_income():
    # Ten scrolls dropped and nothing was sold: that is 600k earned, not an idle hour.
    snaps = [scroll_snap(HOUR * 9 + 10, 1000, 0), scroll_snap(HOUR * 9 + 20, 1000, 10)]
    out = hourly_income(snaps, now=HOUR * 9 + 30, hours=1, scroll_price=60_000)
    assert out["hours"][0]["delta"] == 600_000


def test_selling_scrolls_is_not_counted_twice():
    # The coins arrive as the scrolls leave: wealth is unchanged, so the hour reports the drops only.
    snaps = [
        scroll_snap(HOUR * 9 + 10, 0, 10),          # 600k of scrolls
        scroll_snap(HOUR * 9 + 20, 600_000, 0),     # sold them
    ]
    out = hourly_income(snaps, now=HOUR * 9 + 30, hours=1, scroll_price=60_000)
    assert out["hours"][0]["delta"] == 0


def test_rows_without_scroll_counts_are_not_compared_with_rows_that_have_them():
    # The first reading predates scroll counting; pairing them would invent a bagful of income.
    snaps = [scroll_snap(HOUR * 9 + 10, 1000, None), scroll_snap(HOUR * 9 + 20, 1000, 800)]
    out = hourly_income(snaps, now=HOUR * 9 + 30, hours=1, scroll_price=60_000)
    assert out["hours"][0]["delta"] == 0


def test_daily_income_counts_scrolls_too():
    snaps = [
        scroll_snap(local(2026, 9, 15, 12, 0), 0, 0),
        scroll_snap(local(2026, 9, 15, 13, 0), 0, 100),
    ]
    out = daily_income(snaps, now=local(2026, 9, 15, 14, 0), days=1, scroll_price=60_000)
    assert out["days"][0]["delta"] == 6_000_000
