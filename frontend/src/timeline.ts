import type { Snapshot, State } from "./types";

export const DAY_S = 86400;
// Snapshots arrive every 60 s while the game is open; a longer gap means "no data".
export const MAX_GAP_S = 90;

export interface Segment {
  from: number;
  to: number;
  state: State;
}

/** Snapshots (oldest first) → merged [from, to) pieces of one state, clipped to [start, end]. */
export function buildSegments(
  snapshots: readonly Snapshot[],
  start: number,
  end: number,
  maxGapS: number = MAX_GAP_S,
): Segment[] {
  const segments: Segment[] = [];
  snapshots.forEach((snapshot, index) => {
    const next = snapshots[index + 1];
    const covered = next ? Math.min(next.ts, snapshot.ts + maxGapS) : snapshot.ts + maxGapS;
    const from = Math.max(snapshot.ts, start);
    const to = Math.min(covered, end);
    if (to <= from) return;
    const last = segments[segments.length - 1];
    if (last && last.state === snapshot.state && Math.abs(last.to - from) < 1) {
      last.to = to;
    } else {
      segments.push({ from, to, state: snapshot.state });
    }
  });
  return segments;
}

/**
 * The 24 h window shown by the timeline. Snapshot timestamps come from the PC's clock and
 * clientNow from the phone's: if the phone lags, ending at clientNow would place the newest
 * snapshot after `end` and drop its (still current) segment, so the end is clamped forward.
 */
export function timelineWindow(snapshots: readonly Snapshot[], clientNow: number): { start: number; end: number } {
  const newestTs = snapshots.length ? snapshots[snapshots.length - 1].ts : clientNow;
  const end = Math.max(clientNow, newestTs);
  return { start: end - DAY_S, end };
}
