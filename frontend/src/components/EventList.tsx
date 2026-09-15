import { dateTimeText } from "../format";
import { eventLabel } from "../labels";
import type { EventItem } from "../types";

export function EventList({ title, events }: { title: string; events: readonly EventItem[] }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {events.length ? (
        <ul className="event-list">
          {events.map((event) => (
            <li key={event.id}>
              <span className="event-kind">{eventLabel(event.kind)}</span>
              <span className="meta">{[event.detail, dateTimeText(event.ts)].filter(Boolean).join(" · ")}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="meta">Henüz olay yok.</p>
      )}
    </section>
  );
}
