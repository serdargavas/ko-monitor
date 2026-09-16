import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IncomeChart } from "../src/components/IncomeChart";
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
});
