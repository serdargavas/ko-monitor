import { getVapidKey, sendTestPush, subscribePush } from "../api.js";
import { el } from "../ui.js";

function base64UrlToBytes(value) {
  const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function sameKey(subscription, keyBytes) {
  const current = subscription.options && subscription.options.applicationServerKey;
  if (!current) return false;
  const bytes = new Uint8Array(current);
  return bytes.length === keyBytes.length && bytes.every((value, index) => value === keyBytes[index]);
}

function isStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
}

function pushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

async function enableNotifications() {
  // iOS only shows the permission prompt when it is requested directly from the tap.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Bildirim izni verilmedi.");
  }
  const registration = await navigator.serviceWorker.ready;
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
  await subscribePush(subscription.toJSON());
}

export default {
  title: "Ayarlar",
  mount(root) {
    const statusLine = el("p", { class: "note" });
    const show = (text, tone = "") => {
      statusLine.textContent = text;
      statusLine.className = `note ${tone}`;
    };
    const enableButton = el("button", { class: "primary", type: "button" }, "Bildirimleri aç");
    const testButton = el("button", { type: "button" }, "Test bildirimi gönder");
    const hints = [];

    if (!isStandalone()) {
      hints.push(el("p", { class: "note warn" },
        "iPhone'da bildirim için önce Safari → Paylaş → Ana Ekrana Ekle ile uygulamayı kur ve ana ekrandaki simgeden aç."));
    }
    if (!pushSupported()) {
      enableButton.disabled = true;
      hints.push(el("p", { class: "note bad" }, "Bu tarayıcı Web Push desteklemiyor (iPhone'da iOS 16.4 veya üstü gerekir)."));
    } else if (Notification.permission === "granted") {
      show("Bildirim izni verilmiş. Aboneliği yenilemek için yine de 'Bildirimleri aç'a dokunabilirsin.", "ok");
    } else if (Notification.permission === "denied") {
      show("Bildirim izni reddedilmiş. iPhone Ayarlar → Bildirimler → KO Monitor'dan izin ver.", "bad");
    }

    enableButton.addEventListener("click", async () => {
      enableButton.disabled = true;
      show("Bildirimler açılıyor…");
      try {
        await enableNotifications();
        show("Bildirimler açık. Şimdi test bildirimi gönderebilirsin.", "ok");
      } catch (error) {
        show(`Açılamadı: ${error.message}`, "bad");
      } finally {
        enableButton.disabled = false;
      }
    });

    testButton.addEventListener("click", async () => {
      testButton.disabled = true;
      show("Gönderiliyor…");
      try {
        const result = await sendTestPush();
        if (result.delivered) show("Test bildirimi gönderildi.", "ok");
        else if (result.subscriptions === 0) show("Kayıtlı abonelik yok. Önce 'Bildirimleri aç'a dokun.", "warn");
        else show("Gönderilemedi. Bilgisayardaki logs\\agent.log dosyasına bak.", "bad");
      } catch (error) {
        show(`Hata: ${error.message}`, "bad");
      } finally {
        testButton.disabled = false;
      }
    });

    root.append(
      el("h1", {}, "Ayarlar"),
      el("section", { class: "card" },
        el("h2", {}, "Bildirimler"),
        ...hints,
        el("div", { class: "buttons" }, enableButton, testButton),
        statusLine),
    );
    return null;
  },
};
