import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { restoreObjectUrlStubs } from "./fakes";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  // setHidden() shadows Document.prototype.hidden on the instance; drop it again.
  Reflect.deleteProperty(document, "hidden");
  Reflect.deleteProperty(navigator, "serviceWorker");
  restoreObjectUrlStubs(); // undoes installStreamFakes()'s URL.createObjectURL/revokeObjectURL stubs
  localStorage.clear();
  window.location.hash = "";
});
