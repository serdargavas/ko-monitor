import { useSyncExternalStore } from "react";

function subscribe(onChange: () => void): () => void {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
}

/** False while the app is in the background (document.hidden). */
export function useVisibility(): boolean {
  return useSyncExternalStore(subscribe, () => !document.hidden, () => true);
}
