import { streamUrl } from "../api.js";
import { el } from "../ui.js";

const QUALITIES = [["low", "Düşük"], ["medium", "Orta"], ["high", "Yüksek"]];
const STORAGE_KEY = "ko-monitor.quality";
const RECONNECT_MS = [1000, 2000, 5000, 10000];
const STATUS_TEXT = {
  minimized: "Oyun penceresi küçültülmüş, görüntü alınamıyor",
  not_found: "Oyun penceresi bulunamadı",
  black: "Ekran siyah",
};

function loadQuality() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return QUALITIES.some(([key]) => key === saved) ? saved : null;
  } catch (error) {
    return null; // storage unavailable: use the server default
  }
}

function saveQuality(quality) {
  try {
    localStorage.setItem(STORAGE_KEY, quality);
  } catch (error) {
    // storage unavailable: the choice lasts until the screen is left
  }
}

export default {
  title: "Canlı",
  mount(root) {
    let quality = loadQuality(); // null → the server's [api] stream_quality
    let socket = null;
    let retryTimer = null;
    let attempts = 0;
    let frameUrl = null;
    let active = true;

    const image = el("img", { class: "live-frame", alt: "Canlı oyun görüntüsü" });
    const overlay = el("div", { class: "live-overlay" }, "Bağlanıyor…");
    const stage = el("div", { class: "live-stage" }, image, overlay);
    const buttons = QUALITIES.map(([key, text]) => el("button", { type: "button", "data-quality": key }, text));
    const fullscreenButton = el("button", { type: "button" }, "Tam ekran");
    const hint = el("p", { class: "meta" });

    function showOverlay(text) {
      overlay.textContent = text;
      overlay.hidden = !text;
    }

    function markQuality() {
      for (const button of buttons) {
        button.classList.toggle("active", button.dataset.quality === quality);
      }
      hint.textContent = (quality ? "" : "Kalite seçilmedi: bilgisayardaki varsayılan kullanılıyor. ")
        + "Telefonu yan çevirince görüntü tam ekran olur.";
    }

    function showFrame(blob) {
      const previous = frameUrl;
      frameUrl = URL.createObjectURL(blob);
      image.src = frameUrl;
      if (previous) URL.revokeObjectURL(previous);
    }

    function connect() {
      clearTimeout(retryTimer);
      retryTimer = null;
      if (!active || socket) return;
      if (document.hidden) {
        showOverlay("Duraklatıldı");
        return;
      }
      showOverlay(attempts ? "Yeniden bağlanıyor…" : "Bağlanıyor…");
      const ws = new WebSocket(streamUrl(quality));
      ws.binaryType = "blob";
      socket = ws;
      ws.onmessage = (event) => {
        if (socket !== ws) return;
        if (typeof event.data === "string") {
          let status = "";
          try {
            status = JSON.parse(event.data).status;
          } catch (error) {
            status = "";
          }
          showOverlay(STATUS_TEXT[status] || "Görüntü bekleniyor…");
          return;
        }
        attempts = 0;
        showOverlay("");
        showFrame(event.data);
      };
      ws.onclose = () => {
        if (socket !== ws) return; // closed on purpose: quality change, page hidden or screen left
        socket = null;
        if (!active || document.hidden) return;
        const delay = RECONNECT_MS[Math.min(attempts, RECONNECT_MS.length - 1)];
        attempts += 1;
        showOverlay(`Bağlantı koptu, ${Math.round(delay / 1000)} sn içinde yeniden denenecek…`);
        retryTimer = setTimeout(connect, delay);
      };
    }

    function disconnect() {
      clearTimeout(retryTimer);
      retryTimer = null;
      const ws = socket;
      socket = null;
      if (ws) ws.close(); // the server stops capturing and encoding for this viewer
    }

    function onVisibility() {
      if (document.hidden) {
        disconnect();
        showOverlay("Duraklatıldı");
      } else {
        attempts = 0;
        connect();
      }
    }

    for (const button of buttons) {
      button.addEventListener("click", () => {
        if (button.dataset.quality === quality) return;
        quality = button.dataset.quality;
        saveQuality(quality);
        markQuality();
        disconnect();
        attempts = 0;
        connect();
      });
    }

    fullscreenButton.hidden = !(stage.requestFullscreen || stage.webkitRequestFullscreen);
    fullscreenButton.addEventListener("click", () => {
      if (stage.requestFullscreen) stage.requestFullscreen().catch(() => {});
      else stage.webkitRequestFullscreen();
    });

    root.append(
      el("div", { class: "live-header" },
        el("h1", {}, "Canlı"),
        el("div", { class: "quality" }, ...buttons, fullscreenButton)),
      stage,
      hint,
    );
    document.body.classList.add("live-mode");
    document.addEventListener("visibilitychange", onVisibility);
    markQuality();
    connect();

    return () => {
      active = false;
      disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      document.body.classList.remove("live-mode");
      if (frameUrl) URL.revokeObjectURL(frameUrl);
    };
  },
};
