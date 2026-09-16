import { clockText, numberText } from "../format";
import type { Income } from "../types";

const HEIGHT = 90;
const GAP = 2;

/** Hourly coin income. Bars are drawn against the largest absolute hour so a quiet day still reads. */
export function IncomeChart({ income }: { income: Income }) {
  const { hours } = income;
  const scale = Math.max(1, ...hours.map((h) => Math.abs(h.delta ?? 0)));
  const width = 100 / Math.max(1, hours.length);
  return (
    <section className="card">
      <h2>Kazanç (son {hours.length} saat)</h2>
      <div className="income" style={{ height: HEIGHT }}>
        {hours.map((hour) => {
          const value = hour.delta;
          const ratio = value === null ? 1 : Math.abs(value) / scale;
          const tone = value === null ? "none" : value >= 0 ? "pos" : "neg";
          const title =
            value === null
              ? `${clockText(hour.start)}: veri yok`
              : `${clockText(hour.start)}: ${numberText(value)}`;
          return (
            <span
              key={hour.start}
              className={`bar bar-${tone}`}
              title={title}
              style={{
                width: `calc(${width}% - ${GAP}px)`,
                height: `${Math.max(2, ratio * HEIGHT)}px`,
              }}
            />
          );
        })}
      </div>
      <p className="meta">
        Saatlik ortalama — 1 sa: {numberText(income.avg_1h && Math.round(income.avg_1h))} · 6 sa:{" "}
        {numberText(income.avg_6h && Math.round(income.avg_6h))} · 24 sa:{" "}
        {numberText(income.avg_24h && Math.round(income.avg_24h))}
      </p>
    </section>
  );
}
