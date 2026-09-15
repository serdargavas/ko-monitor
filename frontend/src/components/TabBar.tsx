import { type Route, ROUTE_TITLES, ROUTES } from "../hooks/useHashRoute";

export function TabBar({ route }: { route: Route }) {
  return (
    <nav className="tabs">
      {ROUTES.map((name) => (
        <a key={name} href={`#/${name}`} data-route={name} className={name === route ? "active" : undefined}>
          {ROUTE_TITLES[name]}
        </a>
      ))}
    </nav>
  );
}
