import { agoText, clockText, numberText } from "../format";
import type { AgentStatus } from "../types";

export function slotsText(status: AgentStatus): string {
  const used = status.slots_used_last;
  const total = status.slots_total_last;
  if (used === null || used === undefined) return "—";
  if (total === null || total === undefined) return numberText(used);
  return `${numberText(used)} / ${numberText(total)}`;
}

/** null is "the panel could not be read", which silences nothing — it must not read as "stopped". */
export function geniePill(active: boolean | null | undefined): { text: string; tone: string } {
  if (active === null || active === undefined) return { text: "Genie bilinmiyor", tone: "off" };
  return active ? { text: "Genie çalışıyor", tone: "genie" } : { text: "Genie durdu", tone: "warn" };
}

export function InventoryCard({ status }: { status: AgentStatus }) {
  const seen = status.inventory_seen_at;
  const seenText =
    seen === null || seen === undefined
      ? "hiç (envanter penceresi açılınca okunur)"
      : `${clockText(seen)} (${agoText(status.server_time - seen)})`;
  const pill = geniePill(status.genie_active);
  return (
    <section className="card">
      <div className="row">
        <h2>Envanter (son görülen)</h2>
        <span className={`badge ${pill.tone}`}>{pill.text}</span>
      </div>
      <dl className="kv">
        <dt>Para</dt>
        <dd>{numberText(status.money_last)}</dd>
        <dt>Slotlar</dt>
        <dd>{slotsText(status)}</dd>
        <dt>Ok</dt>
        <dd>{status.arrow_unlimited ? "∞ sınırsız" : numberText(status.arrow_last)}</dd>
        <dt>Pot</dt>
        <dd>{numberText(status.mana_last)}</dd>
        <dt>Scroll</dt>
        <dd>{numberText(status.scrolls_last)}</dd>
        <dt>Görüldü</dt>
        <dd>{seenText}</dd>
      </dl>
      {status.genie_active === false && (
        <p className="meta">Ölüm, envanter ve ok/pot bildirimleri susturuldu.</p>
      )}
    </section>
  );
}
