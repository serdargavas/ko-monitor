import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { installReloadOnControllerChange } from "./swReload";
import "./styles.css";

if ("serviceWorker" in navigator) {
  if (import.meta.env.PROD) {
    // Built by vite-plugin-pwa from src/sw.ts; the dev server has no worker.
    installReloadOnControllerChange(navigator.serviceWorker, window);
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((error: unknown) => {
      console.error("service worker:", error);
    });
  }
  // A tapped notification asks an already open window to show its page (see src/sw.ts).
  navigator.serviceWorker.addEventListener("message", (event: MessageEvent) => {
    const data = event.data as { type?: unknown; url?: unknown } | null;
    if (data && data.type === "navigate" && typeof data.url === "string") {
      location.hash = new URL(data.url, location.origin).hash || "#/events";
    }
  });
}

const root = document.getElementById("root");
if (!root) throw new Error("#root missing from index.html");
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
