import { useSyncExternalStore } from "react";

/** Tab order; the first route is the default. Push notifications open "/#/events". */
export const ROUTES = ["status", "live", "events", "settings"] as const;
export type Route = (typeof ROUTES)[number];

export const ROUTE_TITLES: Record<Route, string> = {
  status: "Durum",
  live: "Canlı",
  events: "Olaylar",
  settings: "Ayarlar",
};

/** "#/events" or "#events?x" → "events"; anything unknown → "status". */
export function parseRoute(hash: string): Route {
  const name = hash.replace(/^#\/?/, "").split("?")[0];
  return (ROUTES as readonly string[]).includes(name) ? (name as Route) : ROUTES[0];
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

export function useHashRoute(): Route {
  return useSyncExternalStore(subscribe, () => parseRoute(location.hash), () => ROUTES[0]);
}
