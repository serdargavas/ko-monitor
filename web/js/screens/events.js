import { getEvents, getSnapshots } from "../api.js";
import { clockText, el, eventItem, stateLabel } from "../ui.js";

const DAY_S = 86400;
const MAX_GAP_S = 90; // snapshots arrive every 60 s while the game is open; a longer gap means "no data"
const LEGEND_STATES = ["alive", "dead", "disconnected", "frozen", "blind"];

/** Snapshots (oldest first) → merged [from, to) pieces of one state, clipped to [start, end]. */
export function buildSegments(snapshots, start, end, maxGapS = MAX_GAP_S) {
  const segments = [];
  snapshots.forEach((snapshot, index) => {
    const next = snapshots[index + 1];
    const covered = next ? Math.min(next.ts, snapshot.ts + maxGapS) : snapshot.ts + maxGapS;
    const from = Math.max(snapshot.ts, start);
    const to = Math.min(covered, end);
    if (to <= from) return;
    const last = segments[segments.length - 1];
    if (last && last.state === snapshot.state && Math.abs(last.to - from) < 1) {
      last.to = to;
    } else {
      segments.push({ from, to, state: snapshot.state });
    }
  });
  return segments;
}

function timelineCard(snapshots, start, end) {
  const span = end - start;
  const bar = el("div", { class: "timeline", role: "img", "aria-label": "Son 24 saatin durum çizelgesi" });
  for (const segment of buildSegments(snapshots, start, end)) {
    const label = stateLabel(segment.state);
    const left = ((segment.from - start) / span) * 100;
    const width = Math.max(0.2, ((segment.to - segment.from) / span) * 100);
    bar.append(el("span", {
      class: `seg state-${segment.state}`,
      title: `${label.text}: ${clockText(segment.from)}–${clockText(segment.to)}`,
      style: `left: ${left.toFixed(3)}%; width: ${width.toFixed(3)}%`,
    }));
  }
  const axis = el("div", { class: "timeline-axis" });
  for (let i = 0; i <= 4; i += 1) {
    axis.append(el("span", {}, clockText(start + (span * i) / 4)));
  }
  const legend = el("div", { class: "legend" },
    ...LEGEND_STATES.map((state) => el("span", {}, el("i", { class: `dot state-${state}` }), stateLabel(state).text)),
    el("span", {}, el("i", { class: "dot state-none" }), "Veri yok / oyun kapalı"));
  return el("section", { class: "card" }, el("h2", {}, "Son 24 saat"), bar, axis, legend);
}

function listCard(events) {
  return el("section", { class: "card" },
    el("h2", {}, "Tüm olaylar"),
    events.length
      ? el("ul", { class: "event-list" }, ...events.map(eventItem))
      : el("p", { class: "meta" }, "Henüz olay yok."));
}

export default {
  title: "Olaylar",
  mount(root) {
    const refreshButton = el("button", { type: "button" }, "Yenile");
    const errorLine = el("p", { class: "note bad", hidden: true });
    const body = el("div", {}, el("p", { class: "meta" }, "Yükleniyor…"));
    root.append(el("div", { class: "row" }, el("h1", {}, "Olaylar"), refreshButton), errorLine, body);

    let active = true;
    let loading = false;

    async function refresh() {
      if (loading) return;
      loading = true;
      refreshButton.disabled = true;
      const clientNow = Date.now() / 1000;
      const fetchStart = clientNow - DAY_S;
      try {
        const [events, snapshots] = await Promise.all([getEvents(100), getSnapshots(fetchStart)]);
        if (!active) return;
        // Snapshot timestamps come from the PC's clock; clientNow is the phone's. If the
        // phone's clock lags the PC's, using clientNow alone as the end boundary would place
        // the newest snapshot after "end" and buildSegments would drop its (still current)
        // segment. Clamp the boundary forward to cover the newest snapshot we actually have.
        const newestTs = snapshots.length ? snapshots[snapshots.length - 1].ts : clientNow;
        const end = Math.max(clientNow, newestTs);
        const start = end - DAY_S;
        errorLine.hidden = true;
        body.replaceChildren(timelineCard(snapshots, start, end), listCard(events));
      } catch (error) {
        if (!active) return;
        errorLine.textContent = `Bilgisayara ulaşılamıyor (Tailscale açık mı?): ${error.message}`;
        errorLine.hidden = false;
      } finally {
        loading = false;
        refreshButton.disabled = false;
      }
    }

    function onVisibility() {
      if (!document.hidden) refresh();
    }

    refreshButton.addEventListener("click", refresh);
    document.addEventListener("visibilitychange", onVisibility);
    refresh();
    return () => {
      active = false;
      document.removeEventListener("visibilitychange", onVisibility);
    };
  },
};
