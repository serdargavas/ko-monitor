import { useState } from "react";

import { clockText, dayText, numberText } from "../format";
import type { DailyIncome, Income, IncomeBucket } from "../types";

const HEIGHT = 90;
const HOUR_S = 3600;
/** A bucket with no readings gets a stub, not a full-height bar: nothing happened, so nothing looms. */
const NULL_STUB = 5;

type Mode = "hour" | "day";

function amountText(bucket: IncomeBucket): string {
  return bucket.delta === null ? "veri yok" : numberText(bucket.delta);
}

/** Hourly and daily coin income. Bars scale against the largest absolute bucket in the view. */
export function IncomeChart({ income, daily }: { income: Income; daily: DailyIncome }) {
  const [mode, setMode] = useState<Mode>("hour");
  // Phones have no hover, so the bar titles are unreachable there: tapping a bar names it instead.
  const [picked, setPicked] = useState<number | null>(null);

  const buckets: IncomeBucket[] = mode === "hour" ? income.hours : daily.days;
  const last = buckets[buckets.length - 1];
  const selected = buckets.find((b) => b.start === picked) ?? last;
  const scale = Math.max(1, ...buckets.map((b) => Math.abs(b.delta ?? 0)));
  const width = 100 / Math.max(1, buckets.length);
  const known = buckets.filter((b) => b.delta !== null);
  const total = known.reduce((sum, b) => sum + (b.delta ?? 0), 0);
  const best = known.reduce<IncomeBucket | null>(
    (top, b) => (top === null || (b.delta ?? 0) > (top.delta ?? 0) ? b : top),
    null,
  );

  const label = (bucket: IncomeBucket): string => {
    if (mode === "hour") {
      return `${clockText(bucket.start)}–${clockText(bucket.start + HOUR_S)} · ${amountText(bucket)}`;
    }
    // The last day is still running, so its figure is not comparable with the finished ones.
    const running = last && bucket.start === last.start ? " (sürüyor)" : "";
    return `${dayText(bucket.start)} · ${amountText(bucket)}${running}`;
  };

  const show = (next: Mode) => {
    setMode(next);
    setPicked(null); // the newest bucket of the new view, not a stale selection from the old one
  };

  return (
    <section className="card">
      <div className="row">
        <h2>Kazanç (son {buckets.length} {mode === "hour" ? "saat" : "gün"})</h2>
        <span className="seg">
          <button type="button" className={mode === "hour" ? "on" : ""} onClick={() => show("hour")}>
            Saatlik
          </button>
          <button type="button" className={mode === "day" ? "on" : ""} onClick={() => show("day")}>
            Günlük
          </button>
        </span>
      </div>
      <div className="income" style={{ height: HEIGHT }}>
        {buckets.map((bucket) => {
          const value = bucket.delta;
          const tone = value === null ? "none" : value >= 0 ? "pos" : "neg";
          const height = value === null ? NULL_STUB : Math.max(2, (Math.abs(value) / scale) * HEIGHT);
          return (
            <button
              key={bucket.start}
              type="button"
              className={`bar bar-${tone}${selected && bucket.start === selected.start ? " bar-picked" : ""}`}
              title={label(bucket)}
              aria-label={label(bucket)}
              onClick={() => setPicked(bucket.start)}
              style={{ width: `calc(${width}% - 2px)`, height: `${height}px` }}
            />
          );
        })}
      </div>
      <p className="income-pick">{selected ? label(selected) : "Veri yok"}</p>
      <p className="meta">
        Toplam: {numberText(total)}
        {best && best.delta !== null
          ? ` · En iyi ${mode === "hour" ? "saat" : "gün"}: ${
              mode === "hour" ? clockText(best.start) : dayText(best.start)
            } (${numberText(best.delta)})`
          : ""}
      </p>
      {mode === "hour" ? (
        <p className="meta">
          Saatlik ortalama — 1 sa: {numberText(income.avg_1h && Math.round(income.avg_1h))} · 6 sa:{" "}
          {numberText(income.avg_6h && Math.round(income.avg_6h))} · 24 sa:{" "}
          {numberText(income.avg_24h && Math.round(income.avg_24h))}
        </p>
      ) : (
        <p className="meta">
          Günlük ortalama (bugün hariç) — 7 gün: {numberText(daily.avg_7d && Math.round(daily.avg_7d))} ·
          tümü: {numberText(daily.avg_all && Math.round(daily.avg_all))}
        </p>
      )}
    </section>
  );
}
