import { stateLabel } from "../labels";

export function StateBadge({ state }: { state: string | null }) {
  const label = stateLabel(state);
  return <span className={`badge ${label.tone}`}>{label.text}</span>;
}
