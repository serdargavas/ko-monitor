"""Hourly coin income, derived from the snapshots the agent already writes every minute.

An hour's income is the sum of the rises between consecutive money readings inside it. Steps
larger than max_jump are dropped: a single OCR misread of the money line would otherwise show as
a billion-coin hour. Real large purchases are dropped by the same rule - this measures farm rate,
not bookkeeping.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ko_monitor.models import Snapshot

HOUR_S = 3600.0


def _bucket(ts: float) -> float:
    return float(int(ts // HOUR_S) * HOUR_S)


def _delta_of(values: Sequence[int], max_jump: int) -> int:
    total = 0
    for previous, current in zip(values, values[1:]):
        step = current - previous
        if abs(step) <= max_jump:
            total += step
    return total


def _average(deltas: Iterable[int | None]) -> float | None:
    known = [d for d in deltas if d is not None]
    return sum(known) / len(known) if known else None


def hourly_income(
    snapshots: Iterable[Snapshot],
    now: float,
    hours: int = 24,
    max_jump: int = 50_000_000,
) -> dict:
    """Oldest hour first. delta is None for an hour with no fresh readings (game or bag closed).

    A snapshot counts as a reading for its hour only when its inventory_seen_at falls in the same
    hour: money_last is stale otherwise and would report a real "no data" hour as zero income.
    """
    newest = _bucket(now)
    starts = [newest - HOUR_S * i for i in range(hours - 1, -1, -1)]
    grouped: dict[float, list[int]] = {start: [] for start in starts}
    seen_last: dict[float, float] = {}
    for snap in snapshots:
        if snap.money_last is None:
            continue
        bucket = _bucket(snap.ts)
        if bucket not in grouped:
            continue
        # money_last only changes while the inventory window is open; every snapshot written with
        # the bag closed just repeats an older number. Counting those as readings turns an hour
        # of AFK-with-the-bag-shut into "delta: 0, samples: 60" instead of the "no data" the spec
        # promises, and those zeros then drag the headline averages down. A snapshot is evidence
        # for an hour only if the inventory was actually seen inside that same hour, and repeats
        # of one reading (same inventory_seen_at, therefore the same number) count once.
        if snap.inventory_seen_at is None or _bucket(snap.inventory_seen_at) != bucket:
            continue
        if seen_last.get(bucket) == snap.inventory_seen_at:
            continue
        seen_last[bucket] = snap.inventory_seen_at
        grouped[bucket].append(int(snap.money_last))

    rows = []
    for start in starts:
        values = grouped[start]
        rows.append({
            "start": start,
            "delta": _delta_of(values, max_jump) if len(values) >= 2 else None,
            "samples": len(values),
        })
    deltas = [row["delta"] for row in rows]
    return {
        "hours": rows,
        "avg_1h": _average(deltas[-1:]),
        "avg_6h": _average(deltas[-6:]),
        "avg_24h": _average(deltas[-24:]),
    }
