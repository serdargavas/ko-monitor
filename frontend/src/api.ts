import type { AgentStatus, EventItem, PushTestResult, Quality, Snapshot } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...options });
  if (!response.ok) {
    throw new ApiError(response.status, `${path}: HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const getStatus = () => request<AgentStatus>("/api/status");
export const getEvents = (limit = 50) => request<EventItem[]>(`/api/events?limit=${limit}`);
export const getSnapshots = (since: number) => request<Snapshot[]>(`/api/snapshots?since=${since}`);
export const getVapidKey = () => request<{ key: string }>("/api/push/vapid-key");
export const sendTest = () => request<PushTestResult>("/api/push/test", { method: "POST" });

/** PushSubscription.toJSON() → POST /api/push/subscribe */
export function subscribe(subscription: PushSubscriptionJSON) {
  return request<{ ok: boolean }>("/api/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscription),
  });
}

/** quality null → the server's configured default ([api] stream_quality). */
export function streamUrl(quality: Quality | null): string {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const query = quality ? `?quality=${encodeURIComponent(quality)}` : "";
  return `${scheme}://${location.host}/api/stream${query}`;
}
