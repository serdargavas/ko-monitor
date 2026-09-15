import { agoText, clockText, numberText } from "../format";
import type { AgentStatus } from "../types";

export function slotsText(status: AgentStatus): string {
  const used = status.slots_used_last;
  const total = status.slots_total_last;
  if (used === null || used === undefined) return "—";
  if (total === null || total === undefined) return numberText(used);
  return `${numberText(used)} / ${numberText(total)}`;
}

export function InventoryCard({ status }: { status: AgentStatus }) {
  const seen = status.inventory_seen_at;
  const seenText =
    seen === null || seen === undefined
      ? "hiç (envanter penceresi açılınca okunur)"
      : `${clockText(seen)} (${agoText(status.server_time - seen)})`;
  return (
    <section className="card">
      <h2>Envanter (son görülen)</h2>
      <dl className="kv">
        <dt>Para</dt>
        <dd>{numberText(status.money_last)}</dd>
        <dt>Slotlar</dt>
        <dd>{slotsText(status)}</dd>
        <dt>Görüldü</dt>
        <dd>{seenText}</dd>
      </dl>
    </section>
  );
}
