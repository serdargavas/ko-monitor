from __future__ import annotations

from datetime import datetime

from ko_monitor.models import Event, EventKind

TITLES = {
    EventKind.DEAD: "💀 Karakter öldü",
    EventKind.INVENTORY_FULL: "🎒 Envanter dolu",
    EventKind.DISCONNECTED: "🔌 Sunucudan düştün",
    EventKind.GAME_CLOSED: "❌ Oyun kapandı",
    EventKind.FROZEN: "🧊 Oyun ekranı dondu",
    EventKind.BLIND: "🙈 İzleme yapılamıyor",
    EventKind.GAME_STARTED: "▶️ Oyun açıldı",
    EventKind.RECOVERED: "✅ Düzeldi",
}


def render(event: Event) -> dict:
    when = datetime.fromtimestamp(event.ts).strftime("%H:%M")
    return {
        "title": TITLES[event.kind],
        "body": f"{event.detail} · {when}" if event.detail else when,
        "url": "/#/events",
        "kind": event.kind.value,
        "ts": event.ts,
    }
