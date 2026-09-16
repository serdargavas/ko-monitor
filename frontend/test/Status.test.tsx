import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Status } from "../src/screens/Status";
import { agentStatus, eventItem, stubFetch } from "./fakes";

describe("Status screen", () => {
  it("shows the badge, HP, inventory and the last five events", async () => {
    const fetchMock = stubFetch({
      "/api/status": agentStatus({ slots_total_last: null }),
      "/api/events": [eventItem(7, "dead", 999_900, "HP 0")],
    });
    render(<Status />);
    const badge = await screen.findByText("Canlı");
    expect(badge.className).toBe("badge ok");
    expect(screen.getByText("Son güncelleme 10 sn önce").className).toBe("meta");
    expect(screen.getByText("Bölge: Moradon")).toBeTruthy();
    expect(screen.getByText("9.718 / 9.996")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("9718");
    expect(screen.getByText("1.234.567")).toBeTruthy();
    expect(screen.getByText("20")).toBeTruthy(); // slot total unknown: used slots only
    expect(screen.getByText("💀 Karakter öldü")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/events?limit=5", { cache: "no-store" });
  });

  it("marks stale data and unreadable values", async () => {
    stubFetch({
      "/api/status": agentStatus({
        updated_at: 999_900,
        state: "frozen",
        readings: null,
        zone_last: null,
        money_last: null,
        inventory_seen_at: null,
      }),
      "/api/events": [],
    });
    render(<Status />);
    expect((await screen.findByText("Son güncelleme 1 dk önce")).className).toBe("meta warn");
    expect(screen.getByText("Donmuş").className).toBe("badge warn");
    expect(screen.getByText("HP: okunamadı")).toBeTruthy();
    expect(screen.getByText("Bölge: bilinmiyor")).toBeTruthy();
    // Slots, arrows and potions each read "—" until the inventory window has been seen.
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.getByText("hiç (envanter penceresi açılınca okunur)")).toBeTruthy();
    expect(screen.getByText("Henüz olay yok.")).toBeTruthy();
  });

  it("shows arrow and mana counts and the genie state", async () => {
    stubFetch({
      "/api/status": agentStatus({ arrow_last: 6380, mana_last: 4150, genie_active: true }),
      "/api/events": [],
    });
    render(<Status />);
    expect(await screen.findByText(/6\.380/)).toBeTruthy();
    expect(screen.getByText(/4\.150/)).toBeTruthy();
    expect(screen.getByText(/Genie çalışıyor/)).toBeTruthy();
  });

  it("shows the genie state as unknown when it has not been read", async () => {
    stubFetch({
      "/api/status": agentStatus({ genie_active: null }),
      "/api/events": [],
    });
    render(<Status />);
    expect(await screen.findByText("Genie bilinmiyor")).toBeTruthy();
  });

  it("shows the genie stopped state and mentions silenced alerts", async () => {
    stubFetch({
      "/api/status": agentStatus({ genie_active: false }),
      "/api/events": [],
    });
    render(<Status />);
    expect(await screen.findByText("Genie durdu")).toBeTruthy();
    expect(screen.getByText(/bildirimleri susturuldu/)).toBeTruthy();
  });

  it("does not claim alerts are silenced when the genie state is unknown", async () => {
    stubFetch({
      "/api/status": agentStatus({ genie_active: null }),
      "/api/events": [],
    });
    render(<Status />);
    await screen.findByText("Genie bilinmiyor");
    expect(screen.queryByText(/susturuldu/)).toBeNull();
  });

  it("says when the PC cannot be reached", async () => {
    stubFetch({ "/api/status": new TypeError("Failed to fetch"), "/api/events": [] });
    render(<Status />);
    expect(await screen.findByText("Bilgisayara ulaşılamıyor (Tailscale açık mı?): Failed to fetch")).toBeTruthy();
    expect(screen.getByText("Yükleniyor…")).toBeTruthy();
  });
});
