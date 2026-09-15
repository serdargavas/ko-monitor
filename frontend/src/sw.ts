/// <reference lib="webworker" />
import { cacheNames, clientsClaim } from "workbox-core";
import { matchPrecache, precache } from "workbox-precaching";
import {
  classifyRequest,
  NETWORK_TIMEOUT_MS,
  notificationOptions,
  notificationTarget,
  parsePushPayload,
  RUNTIME_CACHE,
  staleCaches,
} from "./swHelpers";

declare const self: ServiceWorkerGlobalScope;

// vite-plugin-pwa replaces self.__WB_MANIFEST with the build's file list (revisioned), so a new
// build installs a new precache without a hand-bumped cache name.
precache(self.__WB_MANIFEST);
self.skipWaiting();
clientsClaim();

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(staleCaches(keys, [cacheNames.precache, RUNTIME_CACHE]).map((key) => caches.delete(key)))),
  );
});

function timeout(ms: number): Promise<never> {
  return new Promise((_, reject) => setTimeout(() => reject(new Error("network timeout")), ms));
}

async function cachedCopy(request: Request): Promise<Response | undefined> {
  return (await caches.match(request, { cacheName: RUNTIME_CACHE })) ?? (await matchPrecache(request.url));
}

async function networkFirst(request: Request, navigate: boolean): Promise<Response> {
  const network = fetch(request).then((response) => {
    if (response.ok) {
      const copy = response.clone();
      void caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
    }
    return response;
  });
  network.catch(() => undefined); // a late failure after the timeout is not an unhandled rejection
  try {
    return await Promise.race([network, timeout(NETWORK_TIMEOUT_MS)]);
  } catch {
    const cached = await cachedCopy(request);
    if (cached) return cached;
    try {
      return await network; // timed out with nothing cached: a slow answer beats none
    } catch {
      // Offline: only page loads get the app shell; a missing script or icon must not become HTML.
      if (navigate) {
        const shell = await matchPrecache("/index.html");
        if (shell) return shell;
      }
      return Response.error();
    }
  }
}

// Network first (the PC is the only source of truth), cached copy when slow or offline.
// /api/*, non-GET requests and WebSockets are never answered by the worker.
self.addEventListener("fetch", (event) => {
  const kind = classifyRequest(event.request, self.location.origin);
  if (kind !== "navigate" && kind !== "static") return;
  event.respondWith(networkFirst(event.request, kind === "navigate"));
});

self.addEventListener("push", (event) => {
  const { title, options } = notificationOptions(parsePushPayload(event.data, Date.now() / 1000));
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = notificationTarget(event.notification.data, self.location.origin);
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) {
          client.postMessage({ type: "navigate", url: target });
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
