import { useState } from "react";

import { clockText, numberText } from "../format";
import type { Income, IncomeHour } from "../types";

const HEIGHT = 90;
const HOUR_S = 3600;
/** An hour with no readings gets a stub, not a full-height bar: nothing happened, so nothing looms. */
const NULL_STUB = 5;

function hourText(hour: IncomeHour): string {
  const span = `${clockText(hour.start)}–${clockText(hour.start + HOUR_S)}`;
  return hour.delta === null ? `${span} · veri yok` : `${span} · ${numberText(hour.delta)}`;
}

/** Hourly coin income. Bars scale against the largest absolute hour so a quiet day still reads. */
export function IncomeChart({ income }: { income: Income }) {
  const { hours } = income;
  // Phones have no hover, so the bar titles are unreachable there: tapping a bar names it instead.
  const [picked, setPicked] = useState<number | null>(null);
  const selected = hours.find((h) => h.start === picked) ?? hours[hours.length - 1];
  const scale = Math.max(1, ...hours.map((h) => Math.abs(h.delta ?? 0)));
  const width = 100 / Math.max(1, hours.length);
  const known = hours.filter((h) => h.delta !== null);
  const total = known.reduce((sum, h) => sum + (h.delta ?? 0), 0);
  const best = known.reduce<IncomeHour | null>(
    (top, h) => (top === null || (h.delta ?? 0) > (top.delta ?? 0) ? h : top),
    null,
  );
  return (
    <section className="card">
      <h2>Kazanç (son {hours.length} saat)</h2>
      <div className="income" style={{ height: HEIGHT }}>
        {hours.map((hour) => {
          const value = hour.delta;
          const tone = value === null ? "none" : value >= 0 ? "pos" : "neg";
          const height = value === null ? NULL_STUB : Math.max(2, (Math.abs(value) / scale) * HEIGHT);
          return (
            <button
              key={hour.start}
              type="button"
              className={`bar bar-${tone}${selected && hour.start === selected.start ? " bar-picked" : ""}`}
              title={hourText(hour)}
              aria-label={hourText(hour)}
              onClick={() => setPicked(hour.start)}
              style={{ width: `calc(${width}% - 2px)`, height: `${height}px` }}
            />
          );
        })}
      </div>
      <p className="income-pick">{selected ? hourText(selected) : "Veri yok"}</p>
      <p className="meta">
        Toplam: {numberText(total)}
        {best && best.delta !== null ? ` · En iyi saat: ${clockText(best.start)} (${numberText(best.delta)})` : ""}
      </p>
      <p className="meta">
        Saatlik ortalama — 1 sa: {numberText(income.avg_1h && Math.round(income.avg_1h))} · 6 sa:{" "}
        {numberText(income.avg_6h && Math.round(income.avg_6h))} · 24 sa:{" "}
        {numberText(income.avg_24h && Math.round(income.avg_24h))}
      </p>
    </section>
  );
}
