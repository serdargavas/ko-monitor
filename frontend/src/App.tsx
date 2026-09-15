import { type ComponentType, useEffect } from "react";
import { TabBar } from "./components/TabBar";
import { type Route, ROUTE_TITLES, useHashRoute } from "./hooks/useHashRoute";
import { Events } from "./screens/Events";
import { Live } from "./screens/Live";
import { Settings } from "./screens/Settings";
import { Status } from "./screens/Status";

const SCREENS: Record<Route, ComponentType> = {
  status: Status,
  live: Live,
  events: Events,
  settings: Settings,
};

export function App() {
  const route = useHashRoute();
  const Screen = SCREENS[route];

  useEffect(() => {
    document.title = `${ROUTE_TITLES[route]} · KO Monitor`;
  }, [route]);

  return (
    <>
      <main id="screen">
        <Screen key={route} />
      </main>
      <TabBar route={route} />
    </>
  );
}
