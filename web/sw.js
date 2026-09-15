const CACHE = "ko-monitor-v3";
// Every file under web/js must be listed (tests/test_web.py checks it). Bump CACHE when this list changes.
const SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/manifest.webmanifest",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/js/app.js",
  "/js/api.js",
  "/js/ui.js",
  "/js/screens/events.js",
  "/js/screens/live.js",
  "/js/screens/settings.js",
  "/js/screens/status.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

// Network first (the PC is the only source of truth), cached shell when offline. API calls are never cached.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("/index.html"))),
  );
});

// Payload is exactly messages.render(): {title, body, url, kind, ts}.
self.addEventListener("push", (event) => {
  let message = { title: "KO Monitor", body: "", url: "/#/events", kind: "unknown", ts: Date.now() / 1000 };
  if (event.data) {
    try {
      message = { ...message, ...event.data.json() };
    } catch (error) {
      message.body = event.data.text();
    }
  }
  event.waitUntil(
    self.registration.showNotification(message.title, {
      body: message.body,
      tag: `${message.kind}-${message.ts}`,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: message.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/#/events", self.location.origin).href;
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
