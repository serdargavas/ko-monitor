import { describe, expect, it } from "vitest";
import {
  classifyRequest,
  notificationOptions,
  notificationTarget,
  parsePushPayload,
  RUNTIME_CACHE,
  shouldCacheAtRuntime,
  staleCaches,
} from "../src/swHelpers";

const ORIGIN = "https://pc.tailnet.ts.net";

function request(path: string, init: { method?: string; mode?: string } = {}) {
  return { method: init.method ?? "GET", mode: init.mode ?? "cors", url: path.includes("://") ? path : ORIGIN + path };
}

describe("classifyRequest", () => {
  it("never lets the worker answer API calls, POSTs, WebSockets or other hosts", () => {
    expect(classifyRequest(request("/api/status"), ORIGIN)).toBe("api");
    expect(classifyRequest(request("/api/stream?quality=low"), ORIGIN)).toBe("api");
    expect(classifyRequest(request("/api/push/test", { method: "POST" }), ORIGIN)).toBe("ignore");
    expect(classifyRequest(request("/", { method: "POST", mode: "navigate" }), ORIGIN)).toBe("ignore");
    expect(classifyRequest(request("wss://pc.tailnet.ts.net/api/stream"), ORIGIN)).toBe("ignore");
    expect(classifyRequest(request("https://example.com/x.js"), ORIGIN)).toBe("ignore");
  });

  it("tells page loads from static files", () => {
    expect(classifyRequest(request("/", { mode: "navigate" }), ORIGIN)).toBe("navigate");
    expect(classifyRequest(request("/assets/index-abc.js"), ORIGIN)).toBe("static");
    expect(classifyRequest(request("/icons/icon-192.png", { mode: "no-cors" }), ORIGIN)).toBe("static");
  });
});

describe("push payload", () => {
  it("shows messages.render() fields", () => {
    const payload = { title: "💀 Karakter öldü", body: "HP 0 · 14:05", url: "/#/events", kind: "dead", ts: 1700000000.5 };
    const message = parsePushPayload({ json: () => payload, text: () => "" }, 1);
    expect(notificationOptions(message)).toEqual({
      title: "💀 Karakter öldü",
      options: {
        body: "HP 0 · 14:05",
        tag: "dead-1700000000.5",
        icon: "/icons/icon-192.png",
        badge: "/icons/icon-192.png",
        data: { url: "/#/events" },
      },
    });
  });

  it("falls back to defaults and plain text", () => {
    expect(parsePushPayload(null, 42)).toEqual({ title: "KO Monitor", body: "", url: "/#/events", kind: "unknown", ts: 42 });
    const text = parsePushPayload(
      {
        json: () => {
          throw new SyntaxError("bad json");
        },
        text: () => "düz metin",
      },
      42,
    );
    expect(text.body).toBe("düz metin");
    expect(text.title).toBe("KO Monitor");
  });

  it("opens the notification URL, else the events screen", () => {
    expect(notificationTarget({ url: "/#/status" }, ORIGIN)).toBe(`${ORIGIN}/#/status`);
    expect(notificationTarget(null, ORIGIN)).toBe(`${ORIGIN}/#/events`);
    expect(notificationTarget({ url: 5 }, ORIGIN)).toBe(`${ORIGIN}/#/events`);
  });

  it("resolves relative and hash URLs same-origin", () => {
    expect(notificationTarget({ url: "/#/events" }, ORIGIN)).toBe(`${ORIGIN}/#/events`);
    expect(notificationTarget({ url: "#/live" }, ORIGIN)).toBe(`${ORIGIN}/#/live`);
  });

  it("never opens a foreign origin, even a protocol-relative one", () => {
    expect(notificationTarget({ url: "https://evil.example/" }, ORIGIN)).toBe(`${ORIGIN}/#/events`);
    expect(notificationTarget({ url: "//evil.example/x" }, ORIGIN)).toBe(`${ORIGIN}/#/events`);
  });
});

describe("shouldCacheAtRuntime", () => {
  it("never re-copies a precached (hashed build) file into the runtime cache", () => {
    const getCacheKeyForURL = (url: string) => (url.endsWith("/assets/index-abc123.js") ? `${url}?__WB_REVISION__=x` : undefined);
    expect(shouldCacheAtRuntime(`${ORIGIN}/assets/index-abc123.js`, getCacheKeyForURL)).toBe(false);
  });

  it("caches responses that are not part of the build's precache manifest", () => {
    const getCacheKeyForURL = () => undefined;
    expect(shouldCacheAtRuntime(`${ORIGIN}/api/thumbnail.jpg`, getCacheKeyForURL)).toBe(true);
  });
});

describe("staleCaches", () => {
  it("deletes the hand-versioned caches of the old worker", () => {
    const precache = `workbox-precache-v2-${ORIGIN}/`;
    expect(staleCaches(["ko-monitor-v4", precache, RUNTIME_CACHE], [precache, RUNTIME_CACHE])).toEqual(["ko-monitor-v4"]);
  });
});
