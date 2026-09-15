import { getEvents, getStatus } from "../api";
import { EventList } from "../components/EventList";
import { HpBar } from "../components/HpBar";
import { InventoryCard } from "../components/InventoryCard";
import { StateBadge } from "../components/StateBadge";
import { agoText, unreachableText } from "../format";
import { usePolling } from "../hooks/usePolling";
import type { AgentStatus } from "../types";

const POLL_MS = 5000;
const STALE_S = 30; // the agent publishes every 2 s (10 s while the game is closed)

async function loadStatus() {
  const [status, events] = await Promise.all([getStatus(), getEvents(5)]);
  return { status, events };
}

function StateCard({ status }: { status: AgentStatus }) {
  let updated = "Ajan henüz veri göndermedi";
  let stale = true;
  if (status.updated_at !== null && status.updated_at !== undefined) {
    const age = status.server_time - status.updated_at;
    stale = age > STALE_S;
    updated = `Son güncelleme ${agoText(age)}`;
  }
  return (
    <section className="card">
      <div className="row">
        <StateBadge state={status.state} />
        <span className={stale ? "meta warn" : "meta"}>{updated}</span>
      </div>
      <p className="meta">{status.zone_last ? `Bölge: ${status.zone_last}` : "Bölge: bilinmiyor"}</p>
      <HpBar readings={status.readings} />
    </section>
  );
}

export function Status() {
  const { data, error } = usePolling(loadStatus, POLL_MS);
  return (
    <>
      <h1>Durum</h1>
      {/* Keep the last good data on screen; only say that it is not fresh. */}
      {error && <p className="note bad">{unreachableText(error)}</p>}
      {data ? (
        <div>
          <StateCard status={data.status} />
          <InventoryCard status={data.status} />
          <EventList title="Son olaylar" events={data.events} />
        </div>
      ) : (
        <div>
          <p className="meta">Yükleniyor…</p>
        </div>
      )}
    </>
  );
}
