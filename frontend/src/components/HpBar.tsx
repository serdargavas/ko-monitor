import { numberText } from "../format";
import type { Readings } from "../types";

export function HpBar({ readings }: { readings: Readings | null }) {
  const hp = readings ? readings.hp : null;
  const max = readings ? readings.hp_max : null;
  if (hp === null || hp === undefined || !max) {
    return <p className="meta">HP: okunamadı</p>;
  }
  const percent = Math.max(0, Math.min(100, (hp / max) * 100));
  return (
    <div>
      <div className="row">
        <span>HP</span>
        <span>{`${numberText(hp)} / ${numberText(max)}`}</span>
      </div>
      <div className="hpbar" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={hp}>
        <span style={{ width: `${percent.toFixed(1)}%` }} />
      </div>
    </div>
  );
}
