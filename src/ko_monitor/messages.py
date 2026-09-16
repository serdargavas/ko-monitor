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
    EventKind.TEST: "🔔 Test bildirimi",
}


# The blind alert is the one that invites a wrong move: the picture stops while the game keeps
# running, so the body says so instead of letting a stale screen look like a dead client.
_HINTS = {
    EventKind.BLIND: "Ekran kapalı olabilir; oyun çalışmaya devam ediyor olabilir, kapatma.",
}


def render(event: Event) -> dict:
    when = datetime.fromtimestamp(event.ts).strftime("%H:%M")
    body = f"{event.detail} · {when}" if event.detail else when
    hint = _HINTS.get(event.kind)
    return {
        "title": TITLES[event.kind],
        "body": f"{body} — {hint}" if hint else body,
        "url": "/#/events",
        "kind": event.kind.value,
        "ts": event.ts,
    }
