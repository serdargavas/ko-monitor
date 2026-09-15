import { getEvents, getSnapshots } from "../api";
import { EventList } from "../components/EventList";
import { Timeline } from "../components/Timeline";
import { unreachableText } from "../format";
import { usePolling } from "../hooks/usePolling";
import { DAY_S, timelineWindow } from "../timeline";

async function loadEvents() {
  const clientNow = Date.now() / 1000;
  const [events, snapshots] = await Promise.all([getEvents(100), getSnapshots(clientNow - DAY_S)]);
  return { events, snapshots, ...timelineWindow(snapshots, clientNow) };
}

export function Events() {
  // No timer: loads on open, when the app comes back to the foreground and on "Yenile".
  const { data, error, loading, refresh } = usePolling(loadEvents, null);
  return (
    <>
      <div className="row">
        <h1>Olaylar</h1>
        <button type="button" disabled={loading} onClick={() => void refresh()}>
          Yenile
        </button>
      </div>
      {error && <p className="note bad">{unreachableText(error)}</p>}
      {data ? (
        <div>
          <Timeline snapshots={data.snapshots} start={data.start} end={data.end} />
          <EventList title="Tüm olaylar" events={data.events} />
        </div>
      ) : (
        <div>
          <p className="meta">Yükleniyor…</p>
        </div>
      )}
    </>
  );
}
