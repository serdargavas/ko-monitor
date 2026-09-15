import { beforeEach, describe, expect, it, vi } from "vitest";
import { base64UrlToBytes, enableNotifications, serviceWorkerReady } from "../src/push";
import { stubFetch } from "./fakes";

function fakeSubscription(keyBytes: number[]) {
  return {
    options: { applicationServerKey: new Uint8Array(keyBytes).buffer },
    unsubscribe: vi.fn().mockResolvedValue(true),
    toJSON: () => ({ endpoint: "https://web.push.apple.com/abc", keys: { p256dh: "p", auth: "a" } }),
  };
}

function installPush(existing: ReturnType<typeof fakeSubscription> | null, ready?: Promise<unknown>) {
  const created = fakeSubscription([1, 2, 3]);
  const pushManager = {
    getSubscription: vi.fn().mockResolvedValue(existing),
    subscribe: vi.fn().mockResolvedValue(created),
  };
  const registration = { pushManager };
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { ready: ready ?? Promise.resolve(registration) },
  });
  vi.stubGlobal("Notification", { permission: "default", requestPermission: vi.fn().mockResolvedValue("granted") });
  vi.stubGlobal("PushManager", function PushManager() {});
  return pushManager;
}

describe("push", () => {
  beforeEach(() => {
    stubFetch({ "/api/push/vapid-key": { key: "AQID" }, "/api/push/subscribe": { ok: true } });
  });

  it("decodes base64url VAPID keys", () => {
    expect([...base64UrlToBytes("AQID")]).toEqual([1, 2, 3]);
    expect([...base64UrlToBytes("-_8")]).toEqual([251, 255]);
  });

  it("gives up waiting for the service worker after 5 s with a Turkish hint", async () => {
    vi.useFakeTimers();
    installPush(null, new Promise(() => {}));
    const waiting = serviceWorkerReady().catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(5000);
    await expect(waiting).resolves.toBe("Servis çalışanı hazır değil — sayfayı yenileyip tekrar dene");
  });

  it("refuses without permission", async () => {
    installPush(null);
    vi.stubGlobal("Notification", { permission: "default", requestPermission: vi.fn().mockResolvedValue("denied") });
    await expect(enableNotifications()).rejects.toThrow("Bildirim izni verilmedi.");
  });

  it("subscribes with the VAPID key and posts the subscription", async () => {
    const pushManager = installPush(null);
    await enableNotifications();
    const options = pushManager.subscribe.mock.calls[0][0];
    expect(options.userVisibleOnly).toBe(true);
    expect([...options.applicationServerKey]).toEqual([1, 2, 3]);
    expect(fetch).toHaveBeenLastCalledWith("/api/push/subscribe", expect.objectContaining({ method: "POST" }));
  });

  it("keeps a subscription made with the same key", async () => {
    const existing = fakeSubscription([1, 2, 3]);
    const pushManager = installPush(existing);
    await enableNotifications();
    expect(existing.unsubscribe).not.toHaveBeenCalled();
    expect(pushManager.subscribe).not.toHaveBeenCalled();
  });

  it("resubscribes when the PC's VAPID key changed", async () => {
    const existing = fakeSubscription([9, 9, 9]);
    const pushManager = installPush(existing);
    await enableNotifications();
    expect(existing.unsubscribe).toHaveBeenCalledOnce();
    expect(pushManager.subscribe).toHaveBeenCalledOnce();
  });
});
