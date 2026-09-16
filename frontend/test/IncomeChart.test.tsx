import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IncomeChart } from "../src/components/IncomeChart";
import { clockText } from "../src/format";
import type { Income } from "../src/types";

const HOUR = 3600;

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

describe("IncomeChart", () => {
  it("draws one bar per hour", () => {
    const { container } = render(<IncomeChart income={income()} />);
    expect(container.querySelectorAll(".bar")).toHaveLength(3);
  });

  it("shows the averages in tr-TR", () => {
    render(<IncomeChart income={income()} />);
    expect(screen.getByText(/5\.000\.000/)).toBeTruthy();
  });

  it("marks hours without data", () => {
    render(<IncomeChart income={income()} />);
    expect(screen.getByTitle(/veri yok/i)).toBeTruthy();
  });

  it("renders an empty history without crashing", () => {
    render(<IncomeChart income={income({ hours: [], avg_1h: null, avg_6h: null, avg_24h: null })} />);
    expect(screen.getByText(/Kazanç/)).toBeTruthy();
  });

  // The clock text follows the phone's time zone, so the expectations are built from the same
  // formatter the app uses; the amounts beside them are what these tests really pin.
  const span = (hour: number) => `${clockText(HOUR * hour)}–${clockText(HOUR * (hour + 1))}`;
  const pickText = (container: HTMLElement) => container.querySelector(".income-pick")?.textContent;

  it("names the newest hour without being touched", () => {
    // Phones have no hover, so the figure has to be on screen before anything is tapped.
    const { container } = render(<IncomeChart income={income()} />);
    expect(pickText(container)).toBe(`${span(12)} · -2.000.000`);
  });

  it("names the hour whose bar was tapped", () => {
    const { container } = render(<IncomeChart income={income()} />);
    fireEvent.click(container.querySelectorAll(".bar")[0]);
    expect(pickText(container)).toBe(`${span(10)} · 12.000.000`);
  });

  it("says so when the tapped hour has no data", () => {
    const { container } = render(<IncomeChart income={income()} />);
    fireEvent.click(container.querySelectorAll(".bar")[1]);
    expect(pickText(container)).toBe(`${span(11)} · veri yok`);
  });

  it("draws an hour without data as a stub, not a full-height bar", () => {
    const { container } = render(<IncomeChart income={income()} />);
    const [first, none] = Array.from(container.querySelectorAll<HTMLElement>(".bar"));
    // An empty hour must not tower over a real one: it is the tallest bar only if this breaks.
    expect(parseFloat(none.style.height)).toBeLessThan(parseFloat(first.style.height));
    expect(parseFloat(none.style.height)).toBeLessThanOrEqual(6);
  });

  it("totals only the hours that have data", () => {
    render(<IncomeChart income={income()} />);
    expect(screen.getByText(/Toplam: 10\.000\.000/)).toBeTruthy();
  });

  it("names the best hour", () => {
    render(<IncomeChart income={income()} />);
    expect(screen.getByText(`Toplam: 10.000.000 · En iyi saat: ${clockText(HOUR * 10)} (12.000.000)`)).toBeTruthy();
  });
});
