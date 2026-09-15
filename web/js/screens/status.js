import { getEvents, getStatus } from "../api.js";
import { agoText, clockText, el, eventItem, numberText, stateLabel } from "../ui.js";

const POLL_MS = 5000;
const STALE_S = 30; // the agent publishes every 2 s (10 s while the game is closed)

function hpBlock(readings) {
  const hp = readings ? readings.hp : null;
  const max = readings ? readings.hp_max : null;
  if (hp === null || hp === undefined || !max) {
    return el("p", { class: "meta" }, "HP: okunamadı");
  }
  const percent = Math.max(0, Math.min(100, (hp / max) * 100));
  return el("div", {},
    el("div", { class: "row" }, el("span", {}, "HP"), el("span", {}, `${numberText(hp)} / ${numberText(max)}`)),
    el("div", { class: "hpbar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": max, "aria-valuenow": hp },
      el("span", { style: `width: ${percent.toFixed(1)}%` })));
}

function stateCard(status) {
  const label = stateLabel(status.state);
  let updated = "Ajan henüz veri göndermedi";
  let stale = true;
  if (status.updated_at !== null && status.updated_at !== undefined) {
    const age = status.server_time - status.updated_at;
    stale = age > STALE_S;
    updated = `Son güncelleme ${agoText(age)}`;
  }
  return el("section", { class: "card" },
    el("div", { class: "row" },
      el("span", { class: `badge ${label.tone}` }, label.text),
      el("span", { class: stale ? "meta warn" : "meta" }, updated)),
    el("p", { class: "meta" }, status.zone_last ? `Bölge: ${status.zone_last}` : "Bölge: bilinmiyor"),
    hpBlock(status.readings));
}

function slotsText(status) {
  const used = status.slots_used_last;
  const total = status.slots_total_last;
  if (used === null || used === undefined) return "—";
  if (total === null || total === undefined) return numberText(used);
  return `${numberText(used)} / ${numberText(total)}`;
}

function inventoryCard(status) {
  const seen = status.inventory_seen_at;
  const slots = slotsText(status);
  const seenText = seen === null || seen === undefined
    ? "hiç (envanter penceresi açılınca okunur)"
    : `${clockText(seen)} (${agoText(status.server_time - seen)})`;
  return el("section", { class: "card" },
    el("h2", {}, "Envanter (son görülen)"),
    el("dl", { class: "kv" },
      el("dt", {}, "Para"), el("dd", {}, numberText(status.money_last)),
      el("dt", {}, "Slotlar"), el("dd", {}, slots),
      el("dt", {}, "Görüldü"), el("dd", {}, seenText)));
}

function eventsCard(events) {
  return el("section", { class: "card" },
    el("h2", {}, "Son olaylar"),
    events.length
      ? el("ul", { class: "event-list" }, ...events.map(eventItem))
      : el("p", { class: "meta" }, "Henüz olay yok."));
}

export default {
  title: "Durum",
  mount(root) {
    const errorLine = el("p", { class: "note bad", hidden: true });
    const body = el("div", {}, el("p", { class: "meta" }, "Yükleniyor…"));
    root.append(el("h1", {}, "Durum"), errorLine, body);

    let active = true;
    let timer = null;

    async function refresh() {
      try {
        const [status, events] = await Promise.all([getStatus(), getEvents(5)]);
        if (!active) return;
        errorLine.hidden = true;
        body.replaceChildren(stateCard(status), inventoryCard(status), eventsCard(events));
      } catch (error) {
        if (!active) return;
        // Keep the last good data on screen; only say that it is not fresh.
        errorLine.textContent = `Bilgisayara ulaşılamıyor (Tailscale açık mı?): ${error.message}`;
        errorLine.hidden = false;
      }
    }

    function start() {
      if (timer !== null) return;
      refresh();
      timer = setInterval(refresh, POLL_MS);
    }

    function stop() {
      clearInterval(timer);
      timer = null;
    }

    function onVisibility() {
      if (document.hidden) stop();
      else start();
    }

    document.addEventListener("visibilitychange", onVisibility);
    if (!document.hidden) start();
    return () => {
      active = false;
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  },
};
