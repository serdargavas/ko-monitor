// Response shapes of the FastAPI server (src/ko_monitor/api.py, status.py, storage.py, stream.py).

export type State = "closed" | "alive" | "dead" | "disconnected" | "frozen" | "blind";

export type EventKind =
  | "game_started"
  | "game_closed"
  | "dead"
  | "disconnected"
  | "frozen"
  | "blind"
  | "recovered"
  | "inventory_full"
  | "arrow_low"
  | "mana_low"
  | "test";

/** dataclasses.asdict(Readings); only the fields the PWA shows are typed. */
export interface Readings {
  hp: number | null;
  hp_max: number | null;
  [field: string]: unknown;
}

/** GET /api/status: {"server_time": now(), **AgentStatus.to_dict()} */
export interface AgentStatus {
  server_time: number;
  updated_at: number | null;
  state: State | null;
  process_running: boolean;
  capture: string | null;
  readings: Readings | null;
  zone_last: string | null;
  money_last: number | null;
  slots_used_last: number | null;
  slots_total_last: number | null;
  inventory_seen_at: number | null;
  arrow_last: number | null;
  mana_last: number | null;
  genie_active: boolean | null;
}

/** One row of GET /api/snapshots (oldest first). */
export interface Snapshot {
  ts: number;
  state: State;
  hp: number | null;
  hp_max: number | null;
  zone: string | null;
  money_last: number | null;
  slots_used_last: number | null;
  slots_total_last: number | null;
  inventory_seen_at: number | null;
}

/** One row of GET /api/events (newest first). */
export interface EventItem {
  id: number;
  ts: number;
  kind: EventKind | string;
  detail: string;
  notified: boolean;
  notified_at: number | null;
}

/** POST /api/push/test */
export interface PushTestResult {
  delivered: boolean;
  subscriptions: number;
}

/** Text message of WS /api/stream; binary messages are JPEG frames. */
export type StreamStatus = "ok" | "minimized" | "not_found" | "black";

export type Quality = "low" | "medium" | "high";

/** One bucket of GET /api/income (an hour) or /api/income/daily (a local day).
 *  delta null = no fresh reading in that bucket, which is not the same as zero income. */
export interface IncomeBucket {
  start: number;
  delta: number | null;
  samples: number;
}

/** @deprecated kept so older imports keep compiling; buckets are hours or days now. */
export type IncomeHour = IncomeBucket;

/** GET /api/income?hours=N (oldest hour first). */
export interface Income {
  hours: IncomeBucket[];
  avg_1h: number | null;
  avg_6h: number | null;
  avg_24h: number | null;
}

/** GET /api/income/daily?days=N (oldest day first; the last day is still running). */
export interface DailyIncome {
  days: IncomeBucket[];
  avg_7d: number | null;
  avg_all: number | null;
}
