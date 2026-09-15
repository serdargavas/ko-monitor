/**
 * Reloads the page once a new service worker takes control of it — the running React bundle
 * would otherwise keep talking to old code while a newer one is already active in the worker.
 * Skips the very first install (no controller existed yet, so there is nothing to refresh away
 * from) and guards against reload loops if controllerchange fires more than once.
 */
export function installReloadOnControllerChange(
  serviceWorker: Pick<ServiceWorkerContainer, "controller" | "addEventListener">,
  win: { location: Pick<Location, "reload"> },
): void {
  if (!serviceWorker.controller) return;
  let reloading = false;
  serviceWorker.addEventListener("controllerchange", () => {
    if (reloading) return;
    reloading = true;
    win.location.reload();
  });
}
