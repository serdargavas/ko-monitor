import { clockText } from "../format";
import { stateLabel } from "../labels";
import { buildSegments } from "../timeline";
import type { Snapshot, State } from "../types";

const LEGEND_STATES: State[] = ["alive", "dead", "disconnected", "frozen", "blind"];

export function Timeline({ snapshots, start, end }: { snapshots: readonly Snapshot[]; start: number; end: number }) {
  const span = end - start;
  return (
    <section className="card">
      <h2>Son 24 saat</h2>
      <div className="timeline" role="img" aria-label="Son 24 saatin durum çizelgesi">
        {buildSegments(snapshots, start, end).map((segment) => {
          const left = ((segment.from - start) / span) * 100;
          const width = Math.max(0.2, ((segment.to - segment.from) / span) * 100);
          return (
            <span
              key={segment.from}
              className={`seg state-${segment.state}`}
              title={`${stateLabel(segment.state).text}: ${clockText(segment.from)}–${clockText(segment.to)}`}
              style={{ left: `${left.toFixed(3)}%`, width: `${width.toFixed(3)}%` }}
            />
          );
        })}
      </div>
      <div className="timeline-axis">
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i}>{clockText(start + (span * i) / 4)}</span>
        ))}
      </div>
      <div className="legend">
        {LEGEND_STATES.map((state) => (
          <span key={state}>
            <i className={`dot state-${state}`} />
            {stateLabel(state).text}
          </span>
        ))}
        <span>
          <i className="dot state-none" />
          Veri yok / oyun kapalı
        </span>
      </div>
    </section>
  );
}
