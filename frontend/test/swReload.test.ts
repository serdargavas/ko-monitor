import { describe, expect, it, vi } from "vitest";
import { installReloadOnControllerChange } from "../src/swReload";

/** Minimal stand-in for navigator.serviceWorker: just enough of EventTarget + .controller. */
class FakeServiceWorkerContainer {
  controller: object | null;
  private listeners: Array<() => void> = [];

  constructor(controller: object | null) {
    this.controller = controller;
  }

  addEventListener(type: string, listener: () => void): void {
    if (type === "controllerchange") this.listeners.push(listener);
  }

  fireControllerChange(): void {
    for (const listener of this.listeners) listener();
  }
}

function fakeWindow() {
  return { location: { reload: vi.fn() } };
}

describe("installReloadOnControllerChange", () => {
  it("does not reload on the very first install (no prior controller)", () => {
    const sw = new FakeServiceWorkerContainer(null);
    const win = fakeWindow();
    installReloadOnControllerChange(sw as unknown as ServiceWorkerContainer, win);
    sw.fireControllerChange();
    expect(win.location.reload).not.toHaveBeenCalled();
  });

  it("reloads once when an update takes control of an already-controlled page", () => {
    const sw = new FakeServiceWorkerContainer({});
    const win = fakeWindow();
    installReloadOnControllerChange(sw as unknown as ServiceWorkerContainer, win);
    sw.fireControllerChange();
    expect(win.location.reload).toHaveBeenCalledTimes(1);
  });

  it("never reloads twice even if controllerchange fires again", () => {
    const sw = new FakeServiceWorkerContainer({});
    const win = fakeWindow();
    installReloadOnControllerChange(sw as unknown as ServiceWorkerContainer, win);
    sw.fireControllerChange();
    sw.fireControllerChange();
    expect(win.location.reload).toHaveBeenCalledTimes(1);
  });
});
