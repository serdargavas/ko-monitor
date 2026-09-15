export type Tone = "ok" | "warn" | "bad" | "off";

export interface StateLabel {
  text: string;
  tone: Tone;
}

export const STATE_LABELS: Record<string, StateLabel> = {
  alive: { text: "Canlı", tone: "ok" },
  dead: { text: "Ölü", tone: "bad" },
  disconnected: { text: "Bağlantı koptu", tone: "bad" },
  frozen: { text: "Donmuş", tone: "warn" },
  blind: { text: "Kör (izlenemiyor)", tone: "warn" },
  closed: { text: "Oyun kapalı", tone: "off" },
};

// Same titles as src/ko_monitor/messages.py TITLES.
export const EVENT_LABELS: Record<string, string> = {
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

export function stateLabel(state: string | null | undefined): StateLabel {
  return (state && STATE_LABELS[state]) || { text: "Bilinmiyor", tone: "off" };
}

export function eventLabel(kind: string): string {
  return EVENT_LABELS[kind] || kind;
}
