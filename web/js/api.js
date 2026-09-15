export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  if (!response.ok) {
    throw new ApiError(response.status, `${path}: HTTP ${response.status}`);
  }
  return response.json();
}

export const getStatus = () => request("/api/status");
export const getEvents = (limit = 50) => request(`/api/events?limit=${limit}`);
export const getSnapshots = (since) => request(`/api/snapshots?since=${since}`);
export const getVapidKey = () => request("/api/push/vapid-key");
export const sendTestPush = () => request("/api/push/test", { method: "POST" });

export function subscribePush(subscriptionJson) {
  return request("/api/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscriptionJson),
  });
}

/** quality null → the server's configured default ([api] stream_quality). */
export function streamUrl(quality) {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const query = quality ? `?quality=${encodeURIComponent(quality)}` : "";
  return `${scheme}://${location.host}/api/stream${query}`;
}
