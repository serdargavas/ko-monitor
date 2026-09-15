import { vi } from "vitest";
import type { AgentStatus, EventItem, Snapshot, State } from "../src/types";

/** Stands in for the browser WebSocket; tests drive it with receive() and serverClose(). */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  binaryType = "blob";
  closed = false;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  static last(): FakeWebSocket {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  }

  /** Client-side close; like a real socket, onclose still fires later (see serverClose). */
  close(): void {
    this.closed = true;
  }

  receive(data: unknown): void {
    this.onmessage?.({ data });
  }

  serverClose(code = 1006, reason = ""): void {
    this.onclose?.({ code, reason });
  }
}

/** Installs FakeWebSocket and counting URL.createObjectURL / revokeObjectURL stubs. */
export function installStreamFakes() {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  let next = 0;
  const createObjectURL = vi.fn(() => `blob:frame-${++next}`);
  const revokeObjectURL = vi.fn();
  Object.defineProperty(URL, "createObjectURL", { configurable: true, writable: true, value: createObjectURL });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, writable: true, value: revokeObjectURL });
  return { createObjectURL, revokeObjectURL };
}

/** Sets document.hidden and fires visibilitychange (wrap in act() while something is rendered). */
export function setHidden(hidden: boolean): void {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  document.dispatchEvent(new Event("visibilitychange"));
}

/**
 * Replaces fetch: the first route whose key is a prefix of the requested path answers with its
 * value as JSON; an Error value makes fetch reject; unknown paths get 404. Routes are read on
 * every call, so tests may change them between calls.
 */
export function stubFetch(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const path = String(input);
    const key = Object.keys(routes).find((prefix) => path.startsWith(prefix));
    if (key === undefined) return new Response("not found", { status: 404 });
    const body = routes[key];
    if (body instanceof Error) throw body;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function snapshot(ts: number, state: State): Snapshot {
  return {
    ts,
    state,
    hp: null,
    hp_max: null,
    zone: null,
    money_last: null,
    slots_used_last: null,
    slots_total_last: null,
    inventory_seen_at: null,
  };
}

export function agentStatus(overrides: Partial<AgentStatus> = {}): AgentStatus {
  return {
    server_time: 1_000_000,
    updated_at: 999_990,
    state: "alive",
    process_running: true,
    capture: "ok",
    readings: { hp: 9718, hp_max: 9996 },
    zone_last: "Moradon",
    money_last: 1234567,
    slots_used_last: 20,
    slots_total_last: 28,
    inventory_seen_at: 999_700,
    ...overrides,
  };
}

export function eventItem(id: number, kind: string, ts: number, detail = ""): EventItem {
  return { id, ts, kind, detail, notified: true, notified_at: ts };
}
