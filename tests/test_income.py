from ko_monitor.income import hourly_income
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
