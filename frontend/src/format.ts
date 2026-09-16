/** Seconds → "12 sn önce" / "3 dk önce" / "2 sa önce" / "1 gün önce"; null → "hiç". */
export function agoText(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "hiç";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} sn önce`;
  if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
  if (s < 86400) return `${Math.floor(s / 3600)} sa önce`;
  return `${Math.floor(s / 86400)} gün önce`;
}

/** Unix seconds → "14:05" in the phone's time zone. */
export function clockText(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

/** Unix seconds → day, month, hour and minute in tr-TR. */
export function dateTimeText(ts: number): string {
  return new Date(ts * 1000).toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Error line of screens that could not reach the PC; the last good data stays on screen. */
export function unreachableText(error: Error): string {
  return `Bilgisayara ulaşılamıyor (Tailscale açık mı?): ${error.message}`;
}

/** 1234567 → "1.234.567"; null → "—". */
export function numberText(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : Number(value).toLocaleString("tr-TR");
}

/** Unix seconds → "16 Eylül" in the phone's time zone. */
export function dayText(ts: number): string {
  return new Date(ts * 1000).toLocaleDateString("tr-TR", { day: "numeric", month: "long" });
}
