// Pure helpers of the service worker (src/sw.ts), kept free of worker globals so Vitest can test them.

export const RUNTIME_CACHE = "ko-monitor-runtime";
// A phone on a flaky tailnet connection should not stare at a blank screen: after this long the
// cached copy is used if there is one.
export const NETWORK_TIMEOUT_MS = 3000;
export const DEFAULT_URL = "/#/events";

/** "api", "navigate" and "static" are same-origin GETs; everything else (POST, ws:, other hosts) is "ignore". */
export type RequestKind = "api" | "navigate" | "static" | "ignore";

export function classifyRequest(
  request: { method: string; url: string; mode: string },
  origin: string,
): RequestKind {
  if (request.method !== "GET") return "ignore";
  const url = new URL(request.url);
  if (url.origin !== origin) return "ignore";
  if (url.pathname.startsWith("/api/")) return "api";
  return request.mode === "navigate" ? "navigate" : "static";
}

/** Payload is exactly messages.render(): {title, body, url, kind, ts}. */
export interface PushMessage {
  title: string;
  body: string;
  url: string;
  kind: string;
  ts: number;
}

export function parsePushPayload(data: { json(): unknown; text(): string } | null, nowS: number): PushMessage {
  const message: PushMessage = { title: "KO Monitor", body: "", url: DEFAULT_URL, kind: "unknown", ts: nowS };
  if (!data) return message;
  try {
    return { ...message, ...(data.json() as Partial<PushMessage>) };
  } catch {
    return { ...message, body: data.text() };
  }
}

export function notificationOptions(message: PushMessage): { title: string; options: NotificationOptions } {
  return {
    title: message.title,
    options: {
      body: message.body,
      tag: `${message.kind}-${message.ts}`,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: message.url },
    },
  };
}

/** Absolute URL a tapped notification opens (notification.data.url, else the events screen). */
export function notificationTarget(data: unknown, origin: string): string {
  const url = data && typeof data === "object" && "url" in data ? (data as { url: unknown }).url : null;
  return new URL(typeof url === "string" && url ? url : DEFAULT_URL, origin).href;
}

/** Cache names to delete on activate: everything this worker version does not use (e.g. "ko-monitor-v4"). */
export function staleCaches(existing: readonly string[], keep: readonly string[]): string[] {
  return existing.filter((name) => !keep.includes(name));
}
