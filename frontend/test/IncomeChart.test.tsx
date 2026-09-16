import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IncomeChart } from "../src/components/IncomeChart";
import { clockText, dayText } from "../src/format";
import type { Income } from "../src/types";
import { dailyIncome } from "./fakes";

const HOUR = 3600;
const DAY = 86400;

function income(overrides: Partial<Income> = {}): Income {
  return {
    hours: [
      { start: HOUR * 10, delta: 12_000_000, samples: 60 },
      { start: HOUR * 11, delta: null, samples: 0 },
      { start: HOUR * 12, delta: -2_000_000, samples: 30 },
    ],
    avg_1h: -2_000_000,
    avg_6h: 5_000_000,
    avg_24h: 5_000_000,
    ...overrides,
  };
}

function chart(overrides: Partial<Income> = {}) {
  return render(<IncomeChart income={income(overrides)} daily={dailyIncome()} />);
}

// The clock and date text follow the phone's time zone, so the expectations are built from the
// same formatters the app uses; the amounts beside them are what these tests really pin.
const span = (hour: number) => `${clockText(HOUR * hour)}–${clockText(HOUR * (hour + 1))}`;
const pickText = (container: HTMLElement) => container.querySelector(".income-pick")?.textContent;

describe("IncomeChart", () => {
  it("draws one bar per hour", () => {
    const { container } = chart();
    expect(container.querySelectorAll(".bar")).toHaveLength(3);
  });

  it("shows the averages in tr-TR", () => {
    chart();
    expect(screen.getByText(/5\.000\.000/)).toBeTruthy();
  });

  it("marks hours without data", () => {
    chart();
    expect(screen.getByTitle(/veri yok/i)).toBeTruthy();
  });

  it("renders an empty history without crashing", () => {
    chart({ hours: [], avg_1h: null, avg_6h: null, avg_24h: null });
    expect(screen.getByText(/Kazanç/)).toBeTruthy();
  });

  it("names the newest hour without being touched", () => {
    // Phones have no hover, so the figure has to be on screen before anything is tapped.
    const { container } = chart();
    expect(pickText(container)).toBe(`${span(12)} · -2.000.000`);
  });

  it("names the hour whose bar was tapped", () => {
    const { container } = chart();
    fireEvent.click(container.querySelectorAll(".bar")[0]);
    expect(pickText(container)).toBe(`${span(10)} · 12.000.000`);
  });

  it("says so when the tapped hour has no data", () => {
    const { container } = chart();
    fireEvent.click(container.querySelectorAll(".bar")[1]);
    expect(pickText(container)).toBe(`${span(11)} · veri yok`);
  });

  it("draws an hour without data as a stub, not a full-height bar", () => {
    const { container } = chart();
    const [first, none] = Array.from(container.querySelectorAll<HTMLElement>(".bar"));
    // An empty hour must not tower over a real one: it is the tallest bar only if this breaks.
    expect(parseFloat(none.style.height)).toBeLessThan(parseFloat(first.style.height));
    expect(parseFloat(none.style.height)).toBeLessThanOrEqual(6);
  });

  it("totals only the hours that have data", () => {
    chart();
    expect(screen.getByText(/Toplam: 10\.000\.000/)).toBeTruthy();
  });

  it("names the best hour", () => {
    chart();
    expect(screen.getByText(`Toplam: 10.000.000 · En iyi saat: ${clockText(HOUR * 10)} (12.000.000)`)).toBeTruthy();
  });

  it("switches to the daily view", () => {
    const { container } = chart();
    fireEvent.click(screen.getByText("Günlük"));
    expect(screen.getByText(/Kazanç \(son 3 gün\)/)).toBeTruthy();
    expect(container.querySelectorAll(".bar")).toHaveLength(3);
    expect(screen.getByText(/Toplam: 105\.000\.000/)).toBeTruthy();
  });

  it("marks the running day so its figure is not read as a full day", () => {
    const { container } = chart();
    fireEvent.click(screen.getByText("Günlük"));
    expect(pickText(container)).toBe(`${dayText(DAY * 22)} · 5.000.000 (sürüyor)`);
  });

  it("names the day whose bar was tapped", () => {
    const { container } = chart();
    fireEvent.click(screen.getByText("Günlük"));
    fireEvent.click(container.querySelectorAll(".bar")[1]);
    expect(pickText(container)).toBe(`${dayText(DAY * 21)} · 60.000.000`);
  });

  it("shows the daily averages and says today is left out", () => {
    chart();
    fireEvent.click(screen.getByText("Günlük"));
    expect(screen.getByText(/Günlük ortalama \(bugün hariç\)/)).toBeTruthy();
    expect(screen.getByText(/7 gün: 50\.000\.000/)).toBeTruthy();
  });

  it("forgets the tapped bar when the view changes", () => {
    const { container } = chart();
    fireEvent.click(container.querySelectorAll(".bar")[0]); // pick the oldest hour
    fireEvent.click(screen.getByText("Günlük"));
    fireEvent.click(screen.getByText("Saatlik"));
    // Back on the hourly view it must show the newest hour again, not the stale pick.
    expect(pickText(container)).toBe(`${span(12)} · -2.000.000`);
  });
});
