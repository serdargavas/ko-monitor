import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { parseRoute } from "../src/hooks/useHashRoute";
import { agentStatus, income, stubFetch } from "./fakes";

function goTo(hash: string) {
  act(() => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

describe("App", () => {
  it("parses hash routes and falls back to Durum", () => {
    expect(parseRoute("#/events")).toBe("events");
    expect(parseRoute("#live?x=1")).toBe("live");
    expect(parseRoute("")).toBe("status");
    expect(parseRoute("#/nope")).toBe("status");
  });

  it("shows the four tabs in order and switches screens on hashchange", async () => {
    stubFetch({ "/api/status": agentStatus(), "/api/events": [], "/api/snapshots": [], "/api/income?hours=24": income() });
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
    render(<App />);
    const tabs = screen.getAllByRole("link");
    expect(tabs.map((tab) => tab.getAttribute("href"))).toEqual(["#/status", "#/live", "#/events", "#/settings"]);
    expect(tabs.map((tab) => tab.textContent)).toEqual(["Durum", "Canlı", "Olaylar", "Ayarlar"]);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Durum");
    expect(document.title).toBe("Durum · KO Monitor");
    await screen.findByText("Bölge: Moradon");

    goTo("#/settings");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Ayarlar");
    expect(document.title).toBe("Ayarlar · KO Monitor");
    expect(screen.getByRole("link", { name: "Ayarlar" }).className).toBe("active");
    expect(screen.getByRole("link", { name: "Durum" }).className).toBe("");

    goTo("#/events");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Olaylar");
    await screen.findByText("Son 24 saat");
  });
});
