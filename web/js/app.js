import events from "./screens/events.js";
import settings from "./screens/settings.js";
import status from "./screens/status.js";

// Route name → screen module. The first entry is the default route.
const SCREENS = { status, events, settings };

const root = document.getElementById("screen");
let unmount = null;

function currentRoute() {
  const name = location.hash.replace(/^#\/?/, "").split("?")[0];
  return SCREENS[name] ? name : Object.keys(SCREENS)[0];
}

function render() {
  const route = currentRoute();
  if (unmount) {
    unmount();
    unmount = null;
  }
  root.replaceChildren();
  document.title = `${SCREENS[route].title} · KO Monitor`;
  for (const link of document.querySelectorAll("nav.tabs a")) {
    link.classList.toggle("active", link.dataset.route === route);
  }
  unmount = SCREENS[route].mount(root) || null;
}

window.addEventListener("hashchange", render);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch((error) => console.error("service worker:", error));
  // A tapped notification asks an already open window to show its page (see sw.js).
  navigator.serviceWorker.addEventListener("message", (event) => {
    if (event.data && event.data.type === "navigate") {
      location.hash = new URL(event.data.url, location.origin).hash || "#/events";
    }
  });
}

render();
