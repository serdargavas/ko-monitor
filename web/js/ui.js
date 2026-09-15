export const STATE_LABELS = {
  alive: { text: "Canlı", tone: "ok" },
  dead: { text: "Ölü", tone: "bad" },
  disconnected: { text: "Bağlantı koptu", tone: "bad" },
  frozen: { text: "Donmuş", tone: "warn" },
  blind: { text: "Kör (izlenemiyor)", tone: "warn" },
  closed: { text: "Oyun kapalı", tone: "off" },
};

// Same titles as src/ko_monitor/messages.py TITLES.
export const EVENT_LABELS = {
  game_started: "▶️ Oyun açıldı",
  game_closed: "❌ Oyun kapandı",
  dead: "💀 Karakter öldü",
  disconnected: "🔌 Sunucudan düştün",
  frozen: "🧊 Oyun ekranı dondu",
  blind: "🙈 İzleme yapılamıyor",
  recovered: "✅ Düzeldi",
  inventory_full: "🎒 Envanter dolu",
  test: "🔔 Test bildirimi",
};

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  node.append(...children.filter((child) => child !== null && child !== undefined));
  return node;
}

export function stateLabel(state) {
  return STATE_LABELS[state] || { text: "Bilinmiyor", tone: "off" };
}

export function eventLabel(kind) {
  return EVENT_LABELS[kind] || kind;
}

export function agoText(seconds) {
  if (seconds === null || seconds === undefined) return "hiç";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} sn önce`;
  if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
  if (s < 86400) return `${Math.floor(s / 3600)} sa önce`;
  return `${Math.floor(s / 86400)} gün önce`;
}

export function clockText(ts) {
  return new Date(ts * 1000).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

export function dateTimeText(ts) {
  return new Date(ts * 1000).toLocaleString("tr-TR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export function numberText(value) {
  return value === null || value === undefined ? "—" : Number(value).toLocaleString("tr-TR");
}

export function eventItem(event) {
  const meta = [event.detail, dateTimeText(event.ts)].filter(Boolean).join(" · ");
  return el("li", {}, el("span", { class: "event-kind" }, eventLabel(event.kind)), el("span", { class: "meta" }, meta));
}
