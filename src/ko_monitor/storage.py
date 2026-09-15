from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from ko_monitor.models import Event, Snapshot, State

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots(
  ts REAL NOT NULL,
  state TEXT NOT NULL,
  hp INTEGER, hp_max INTEGER, zone TEXT,
  money_last INTEGER, slots_used_last INTEGER, slots_total_last INTEGER,
  inventory_seen_at REAL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  kind TEXT NOT NULL,
  detail TEXT NOT NULL,
  notified INTEGER NOT NULL DEFAULT 0,
  notified_at REAL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS push_subscriptions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint TEXT NOT NULL UNIQUE,
  keys_json TEXT NOT NULL,
  created_at REAL NOT NULL
);
"""


class Storage:
    """SQLite access. Thread-safe so the API (Plan 2) can share it with the agent loop."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def add_snapshot(self, s: Snapshot) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?,?)",
                (s.ts, s.state.value, s.hp, s.hp_max, s.zone, s.money_last,
                 s.slots_used_last, s.slots_total_last, s.inventory_seen_at),
            )

    def snapshots_since(self, ts: float) -> list[Snapshot]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM snapshots WHERE ts >= ? ORDER BY ts", (ts,)
            ).fetchall()
        return [
            Snapshot(r["ts"], State(r["state"]), r["hp"], r["hp_max"], r["zone"],
                     r["money_last"], r["slots_used_last"], r["slots_total_last"],
                     r["inventory_seen_at"])
            for r in rows
        ]

    def prune_snapshots(self, older_than: float) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM snapshots WHERE ts < ?", (older_than,))
        return cur.rowcount

    def add_event(self, e: Event) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO events(ts, kind, detail) VALUES (?,?,?)",
                (e.ts, e.kind.value, e.detail),
            )
        return int(cur.lastrowid)

    def mark_notified(self, event_id: int, at: float) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE events SET notified = 1, notified_at = ? WHERE id = ?", (at, event_id)
            )

    def recent_events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY ts DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"id": r["id"], "ts": r["ts"], "kind": r["kind"], "detail": r["detail"],
             "notified": bool(r["notified"]), "notified_at": r["notified_at"]}
            for r in rows
        ]

    def add_subscription(self, endpoint: str, keys: dict, now: float) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO push_subscriptions(endpoint, keys_json, created_at) VALUES (?,?,?) "
                "ON CONFLICT(endpoint) DO UPDATE SET keys_json = excluded.keys_json",
                (endpoint, json.dumps(keys), now),
            )

    def subscriptions(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT endpoint, keys_json FROM push_subscriptions ORDER BY id"
            ).fetchall()
        return [{"endpoint": r["endpoint"], "keys": json.loads(r["keys_json"])} for r in rows]

    def delete_subscription(self, endpoint: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
