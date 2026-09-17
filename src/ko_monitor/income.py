"""Income per hour and per day, derived from the snapshots the agent already writes.

Income is the change in *wealth*, not in coins: scrolls waiting in the bag are counted at
scroll_price. Counting them as income when they drop and again as coins when they sell would
report the same earnings twice, and ignoring them would leave hours of looting looking idle.

A bucket's income is the sum of the rises between consecutive money readings inside it. Steps
larger than max_jump are dropped: a single OCR misread of the money line would otherwise show as
a billion-coin hour. Real large purchases are dropped by the same rule - this measures farm rate,
not bookkeeping.

Hours are plain 3600 s blocks, but days are local midnight to local midnight. Bucketing days by
86400 s arithmetic would put the boundary at 03:00 for this user, splitting every night's farming
across two "days".
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, time, timedelta

from ko_monitor.models import Snapshot

HOUR_S = 3600.0
DAY_S = 86400.0


def _hour_bucket(ts: float) -> float:
    return float(int(ts // HOUR_S) * HOUR_S)


def _day_bucket(ts: float) -> float:
    """Local midnight of the day ts falls in."""
    moment = datetime.fromtimestamp(ts)
    return datetime.combine(moment.date(), time.min).timestamp()


def day_starts(now: float, days: int) -> list[float]:
    """Local midnights, oldest first, ending with the day `now` falls in."""
    today = datetime.fromtimestamp(now).date()
    return [
        datetime.combine(today - timedelta(days=offset), time.min).timestamp()
        for offset in range(days - 1, -1, -1)
    ]


def _delta_of(values: Sequence[tuple[int, bool]], max_jump: int) -> int:
    total = 0
    for (previous, had_scrolls), (current, has_scrolls) in zip(values, values[1:]):
        # Rows written before scroll counting existed hold coins only. Subtracting one from a
        # wealth reading would invent a jump the size of the whole bag, so such pairs are skipped.
        if had_scrolls != has_scrolls:
            continue
        step = current - previous
        if abs(step) <= max_jump:
            total += step
    return total


def _average(deltas: Iterable[int | None]) -> float | None:
    known = [d for d in deltas if d is not None]
    return sum(known) / len(known) if known else None


def _collect(
    snapshots: Iterable[Snapshot],
    starts: Sequence[float],
    bucket_of: Callable[[float], float],
    scroll_price: int,
) -> dict[float, list[tuple[int, bool]]]:
    """Money readings per bucket, keeping only readings the inventory window actually produced.

    money_last only changes while the inventory window is open; every snapshot written with the
    bag closed just repeats an older number. Counting those as readings turns a spell of
    AFK-with-the-bag-shut into "delta: 0" instead of "no data", and those zeros then drag the
    headline averages down. A snapshot is evidence for a bucket only if the inventory was seen
    inside that same bucket, and repeats of one reading count once.
    """
    grouped: dict[float, list[tuple[int, bool]]] = {start: [] for start in starts}
    seen_last: dict[float, float] = {}
    for snap in snapshots:
        if snap.money_last is None:
            continue
        bucket = bucket_of(snap.ts)
        if bucket not in grouped:
            continue
        if snap.inventory_seen_at is None or bucket_of(snap.inventory_seen_at) != bucket:
            continue
        if seen_last.get(bucket) == snap.inventory_seen_at:
            continue
        seen_last[bucket] = snap.inventory_seen_at
        has_scrolls = snap.scrolls_last is not None
        wealth = int(snap.money_last) + scroll_price * (snap.scrolls_last or 0)
        grouped[bucket].append((wealth, has_scrolls))
    return grouped


def _rows(
    starts: Sequence[float], grouped: dict[float, list[tuple[int, bool]]], max_jump: int
) -> list[dict]:
    rows = []
    for start in starts:
        values = grouped[start]
        rows.append(
            {
                "start": start,
                "delta": _delta_of(values, max_jump) if len(values) >= 2 else None,
                "samples": len(values),
            }
        )
    return rows


def hourly_income(
    snapshots: Iterable[Snapshot],
    now: float,
    hours: int = 24,
    max_jump: int = 50_000_000,
    scroll_price: int = 60_000,
) -> dict:
    """Oldest hour first. delta is None for an hour with no fresh readings (game or bag closed)."""
    newest = _hour_bucket(now)
    starts = [newest - HOUR_S * offset for offset in range(hours - 1, -1, -1)]
    rows = _rows(starts, _collect(snapshots, starts, _hour_bucket, scroll_price), max_jump)
    deltas = [row["delta"] for row in rows]
    return {
        "hours": rows,
        "avg_1h": _average(deltas[-1:]),
        "avg_6h": _average(deltas[-6:]),
        "avg_24h": _average(deltas[-24:]),
    }


def daily_income(
    snapshots: Iterable[Snapshot],
    now: float,
    days: int = 14,
    max_jump: int = 50_000_000,
    scroll_price: int = 60_000,
) -> dict:
    """Oldest day first, local midnight to local midnight; the last day is still in progress."""
    starts = day_starts(now, days)
    rows = _rows(starts, _collect(snapshots, starts, _day_bucket, scroll_price), max_jump)
    deltas = [row["delta"] for row in rows]
    return {
        "days": rows,
        # The running day is partial, so it is excluded from the averages: a day that is two hours
        # old would otherwise drag "the daily average" down every morning.
        "avg_7d": _average(deltas[-8:-1]),
        "avg_all": _average(deltas[:-1]),
    }
