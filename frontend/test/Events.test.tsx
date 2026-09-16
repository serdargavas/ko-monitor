import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Events } from "../src/screens/Events";
import { DAY_S } from "../src/timeline";
import { eventItem, income, snapshot, stubFetch } from "./fakes";

describe("Events screen", () => {
  it("lists events and draws the 24 h timeline", async () => {
    const now = Date.now() / 1000;
    const fetchMock = stubFetch({
      "/api/events": [eventItem(2, "game_started", now - 120), eventItem(1, "inventory_full", now - 600, "28/28")],
      "/api/snapshots": [snapshot(now - 600, "alive"), snapshot(now - 540, "dead")],
      "/api/income?hours=24": income(),
    });
    render(<Events />);
    expect(await screen.findByText("▶️ Oyun açıldı")).toBeTruthy();
    expect(screen.getByText("🎒 Envanter dolu")).toBeTruthy();
    expect(screen.getByText(/^28\/28 · /)).toBeTruthy();
    expect(screen.getByText("Son 24 saat")).toBeTruthy();
    expect(screen.getByText("Tüm olaylar")).toBeTruthy();
    const bar = screen.getByRole("img", { name: "Son 24 saatin durum çizelgesi" });
    expect([...bar.querySelectorAll(".seg")].map((seg) => seg.className)).toEqual(["seg state-alive", "seg state-dead"]);
    expect(screen.getByText("Veri yok / oyun kapalı")).toBeTruthy();

    expect(fetchMock.mock.calls[0][0]).toBe("/api/events?limit=100");
    const since = Number(new URL(String(fetchMock.mock.calls[1][0]), location.origin).searchParams.get("since"));
    expect(Math.abs(since - (now - DAY_S))).toBeLessThan(5);
  });

  it("shows the income chart above the event list", async () => {
    stubFetch({ "/api/events": [], "/api/snapshots": [], "/api/income?hours=24": income() });
    const { container } = render(<Events />);
    await screen.findByText(/Kazanç/);
    const cards = [...container.querySelectorAll(".card")];
    const incomeIndex = cards.findIndex((card) => /Kazanç/.test(card.textContent ?? ""));
    const timelineIndex = cards.findIndex((card) => /Son 24 saat/.test(card.textContent ?? ""));
    expect(incomeIndex).toBeGreaterThanOrEqual(0);
    expect(timelineIndex).toBeGreaterThanOrEqual(0);
    expect(incomeIndex).toBeLessThan(timelineIndex);
  });

  it("reloads on Yenile and shows an empty list", async () => {
    const fetchMock = stubFetch({ "/api/events": [], "/api/snapshots": [], "/api/income?hours=24": income() });
    render(<Events />);
    expect(await screen.findByText("Henüz olay yok.")).toBeTruthy();
    const button = screen.getByRole("button", { name: "Yenile" }) as HTMLButtonElement;
    await waitFor(() => expect(button.disabled).toBe(false));
    fireEvent.click(button);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
  });
});
