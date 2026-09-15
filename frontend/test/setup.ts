import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  // setHidden() shadows Document.prototype.hidden on the instance; drop it again.
  Reflect.deleteProperty(document, "hidden");
  Reflect.deleteProperty(navigator, "serviceWorker");
  localStorage.clear();
  window.location.hash = "";
});
