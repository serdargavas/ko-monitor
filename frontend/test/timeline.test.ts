import { describe, expect, it } from "vitest";
import { buildSegments, DAY_S, timelineWindow } from "../src/timeline";
import { snapshot } from "./fakes";

describe("buildSegments", () => {
  it("returns no segments for no snapshots", () => {
    expect(buildSegments([], 0, 1000)).toEqual([]);
  });

  it("merges consecutive snapshots of the same state", () => {
    const snapshots = [snapshot(100, "alive"), snapshot(160, "alive"), snapshot(220, "dead")];
    expect(buildSegments(snapshots, 0, 1000)).toEqual([
      { from: 100, to: 220, state: "alive" },
      { from: 220, to: 310, state: "dead" },
    ]);
  });

  it("leaves a gap longer than 90 s as no data", () => {
    const snapshots = [snapshot(100, "alive"), snapshot(400, "alive")];
    expect(buildSegments(snapshots, 0, 1000)).toEqual([
      { from: 100, to: 190, state: "alive" },
      { from: 400, to: 490, state: "alive" },
    ]);
  });

  it("covers a single snapshot for 90 s, clipped to the window", () => {
    expect(buildSegments([snapshot(950, "frozen")], 0, 1000)).toEqual([{ from: 950, to: 1000, state: "frozen" }]);
    expect(buildSegments([snapshot(-50, "blind")], 0, 1000)).toEqual([{ from: 0, to: 40, state: "blind" }]);
  });
});

describe("timelineWindow", () => {
  it("ends at the phone's clock when it is ahead of the newest snapshot", () => {
    expect(timelineWindow([snapshot(1900, "alive")], 2000)).toEqual({ start: 2000 - DAY_S, end: 2000 });
    expect(timelineWindow([], 2000)).toEqual({ start: 2000 - DAY_S, end: 2000 });
  });

  it("keeps the current segment when the phone's clock lags the PC's", () => {
    const snapshots = [snapshot(10_000, "alive"), snapshot(10_060, "dead")];
    const clientNow = 10_000; // phone 60 s behind the PC
    const { start, end } = timelineWindow(snapshots, clientNow);
    expect(end).toBe(10_060);
    expect(start).toBe(10_060 - DAY_S);
    expect(buildSegments(snapshots, start, end)).toEqual([{ from: 10_000, to: 10_060, state: "alive" }]);
    // Ending at the phone's clock would have dropped it:
    expect(buildSegments(snapshots, clientNow - DAY_S, clientNow)).toEqual([]);
  });
});
