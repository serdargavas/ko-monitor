import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Settings } from "../src/screens/Settings";
import { stubFetch } from "./fakes";

const INSTALL_HINT =
  "iPhone'da bildirim için önce Safari → Paylaş → Ana Ekrana Ekle ile uygulamayı kur ve ana ekrandaki simgeden aç.";

function stubStandalone(standalone: boolean) {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: standalone })));
}

function stubPushSupport(permission: NotificationPermission, requested: NotificationPermission = permission) {
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { ready: new Promise(() => {}) } });
  vi.stubGlobal("PushManager", function PushManager() {});
  vi.stubGlobal("Notification", { permission, requestPermission: vi.fn().mockResolvedValue(requested) });
}

/**
 * Explicitly removes serviceWorker/PushManager/Notification instead of relying on jsdom merely
 * lacking them, so this test states its precondition and keeps working even if jsdom adds them.
 * Restores the original descriptors afterwards.
 */
function withoutPushSupport<T>(run: () => T): T {
  const serviceWorkerDescriptor = Object.getOwnPropertyDescriptor(navigator, "serviceWorker");
  const pushManagerDescriptor = Object.getOwnPropertyDescriptor(window, "PushManager");
  const notificationDescriptor = Object.getOwnPropertyDescriptor(window, "Notification");
  Reflect.deleteProperty(navigator, "serviceWorker");
  Reflect.deleteProperty(window, "PushManager");
  Reflect.deleteProperty(window, "Notification");
  try {
    return run();
  } finally {
    if (serviceWorkerDescriptor) Object.defineProperty(navigator, "serviceWorker", serviceWorkerDescriptor);
    if (pushManagerDescriptor) Object.defineProperty(window, "PushManager", pushManagerDescriptor);
    if (notificationDescriptor) Object.defineProperty(window, "Notification", notificationDescriptor);
  }
}

describe("Settings screen", () => {
  it("explains that this browser has no Web Push and how to install the app", () => {
    stubStandalone(false);
    withoutPushSupport(() => {
      render(<Settings />);
      expect(screen.getByText("Bu tarayıcı Web Push desteklemiyor (iPhone'da iOS 16.4 veya üstü gerekir).")).toBeTruthy();
      expect(screen.getByText(INSTALL_HINT)).toBeTruthy();
      expect((screen.getByRole("button", { name: "Bildirimleri aç" }) as HTMLButtonElement).disabled).toBe(true);
    });
  });

  it("tells how to allow a denied permission", () => {
    stubStandalone(true);
    stubPushSupport("denied");
    render(<Settings />);
    const line = screen.getByText("Bildirim izni reddedilmiş. iPhone Ayarlar → Bildirimler → KO Monitor'dan izin ver.");
    expect(line.className).toBe("note bad");
    expect(screen.queryByText(INSTALL_HINT)).toBeNull();
    expect((screen.getByRole("button", { name: "Bildirimleri aç" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("reports a refused permission prompt", async () => {
    stubStandalone(true);
    stubPushSupport("default", "denied");
    render(<Settings />);
    fireEvent.click(screen.getByRole("button", { name: "Bildirimleri aç" }));
    expect((await screen.findByText("Açılamadı: Bildirim izni verilmedi.")).className).toBe("note bad");
  });

  it("reports the test push result", async () => {
    stubStandalone(true);
    stubPushSupport("granted");
    const routes: Record<string, unknown> = { "/api/push/test": { delivered: false, subscriptions: 0 } };
    stubFetch(routes);
    render(<Settings />);
    const testButton = screen.getByRole("button", { name: "Test bildirimi gönder" });
    fireEvent.click(testButton);
    expect((await screen.findByText("Kayıtlı abonelik yok. Önce 'Bildirimleri aç'a dokun.")).className).toBe("note warn");
    routes["/api/push/test"] = { delivered: true, subscriptions: 1 };
    fireEvent.click(testButton);
    expect(await screen.findByText("Test bildirimi gönderildi.")).toBeTruthy();
    routes["/api/push/test"] = { delivered: false, subscriptions: 2 };
    fireEvent.click(testButton);
    expect(await screen.findByText("Gönderilemedi. Bilgisayardaki logs\\agent.log dosyasına bak.")).toBeTruthy();
  });
});
