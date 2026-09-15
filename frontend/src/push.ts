import { getVapidKey, subscribe } from "./api";

// navigator.serviceWorker.ready never settles if the worker failed to install; do not hang the button.
export const SW_READY_TIMEOUT_MS = 5000;

export function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function sameKey(subscription: PushSubscription, keyBytes: Uint8Array): boolean {
  const current = subscription.options && subscription.options.applicationServerKey;
  if (!current) return false;
  const bytes = new Uint8Array(current);
  return bytes.length === keyBytes.length && bytes.every((value, index) => value === keyBytes[index]);
}

/** Opened from the home screen icon (iOS only allows Web Push there). */
export function isStandalone(): boolean {
  const displayMode = typeof window.matchMedia === "function" && window.matchMedia("(display-mode: standalone)").matches;
  return displayMode || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function serviceWorkerReady(timeoutMs: number = SW_READY_TIMEOUT_MS): Promise<ServiceWorkerRegistration> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error("Servis çalışanı hazır değil — sayfayı yenileyip tekrar dene")),
      timeoutMs,
    );
    void navigator.serviceWorker.ready.then((registration) => {
      clearTimeout(timer);
      resolve(registration);
    });
  });
}

/** Permission → VAPID key → (re)subscribe → POST /api/push/subscribe. Errors carry Turkish messages. */
export async function enableNotifications(): Promise<void> {
  // iOS only shows the permission prompt when it is requested directly from the tap.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Bildirim izni verilmedi.");
  }
  const registration = await serviceWorkerReady();
  const { key } = await getVapidKey();
  const keyBytes = base64UrlToBytes(key);
  let subscription = await registration.pushManager.getSubscription();
  if (subscription && !sameKey(subscription, keyBytes)) {
    await subscription.unsubscribe(); // the PC's VAPID key changed; the old subscription cannot be used
    subscription = null;
  }
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes });
  }
  await subscribe(subscription.toJSON());
}
