import { describe, expect, it } from "vitest";
import { agoText, clockText, dateTimeText, numberText, unreachableText } from "../src/format";
import { EVENT_LABELS, eventLabel, STATE_LABELS, stateLabel } from "../src/labels";

describe("format", () => {
  it("groups money with dots like tr-TR", () => {
    expect(numberText(1234567)).toBe("1.234.567");
    expect(numberText(0)).toBe("0");
  });

  it("shows missing numbers as —", () => {
    expect(numberText(null)).toBe("—");
    expect(numberText(undefined)).toBe("—");
  });

  it("says how long ago in seconds, minutes, hours and days", () => {
    expect(agoText(0)).toBe("0 sn önce");
    expect(agoText(59.4)).toBe("59 sn önce");
    expect(agoText(-5)).toBe("0 sn önce");
    expect(agoText(125)).toBe("2 dk önce");
    expect(agoText(7200)).toBe("2 sa önce");
    expect(agoText(90000)).toBe("1 gün önce");
    expect(agoText(null)).toBe("hiç");
  });

  it("formats clock and date times with two digits", () => {
    expect(clockText(1_700_000_000)).toMatch(/^\d{2}:\d{2}$/);
    expect(dateTimeText(1_700_000_000)).toMatch(/^\d{2}[./]\d{2} \d{2}:\d{2}$/);
  });

  it("names the unreachable PC in Turkish", () => {
    expect(unreachableText(new Error("Failed to fetch"))).toBe(
      "Bilgisayara ulaşılamıyor (Tailscale açık mı?): Failed to fetch",
    );
  });
});

describe("labels", () => {
  it("covers every state and event kind of the server", () => {
    expect(Object.keys(STATE_LABELS).sort()).toEqual(["alive", "blind", "closed", "dead", "disconnected", "frozen"]);
    expect(Object.keys(EVENT_LABELS).sort()).toEqual([
      "arrow_low",
      "blind",
      "dead",
      "disconnected",
      "frozen",
      "game_closed",
      "game_started",
      "inventory_full",
      "mana_low",
      "recovered",
      "test",
    ]);
  });

  it("falls back for unknown values", () => {
    expect(stateLabel(null)).toEqual({ text: "Bilinmiyor", tone: "off" });
    expect(stateLabel("dead")).toEqual({ text: "Ölü", tone: "bad" });
    expect(eventLabel("test")).toBe("🔔 Test bildirimi");
    expect(eventLabel("something_new")).toBe("something_new");
  });
});
