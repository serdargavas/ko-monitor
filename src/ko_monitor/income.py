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
    """Oldest hour first. delta is None for an hour with no readings (game or bag closed)."""
    newest = _bucket(now)
    starts = [newest - HOUR_S * i for i in range(hours - 1, -1, -1)]
    grouped: dict[float, list[int]] = {start: [] for start in starts}
    for snap in snapshots:
        if snap.money_last is None:
            continue
        bucket = _bucket(snap.ts)
        if bucket in grouped:
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
