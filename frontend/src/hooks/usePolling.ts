import { useCallback, useEffect, useRef, useState } from "react";
import { useVisibility } from "./useVisibility";

export interface Polling<T> {
  /** Last successful result; kept when a later call fails. */
  data: T | null;
  /** Error of the last call, null after a success. */
  error: Error | null;
  /** A call is in flight. */
  loading: boolean;
  /** Calls fn now unless a call is already in flight. */
  refresh: () => Promise<void>;
}

/**
 * Calls fn when the screen mounts, again every intervalMs while the page is visible (null: no
 * timer), and at once when the page becomes visible again. Nothing runs while hidden or after unmount.
 */
export function usePolling<T>(fn: () => Promise<T>, intervalMs: number | null): Polling<T> {
  const visible = useVisibility();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);
  const fnRef = useRef(fn);
  const mounted = useRef(false);
  const inFlight = useRef(false);

  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    try {
      const value = await fnRef.current();
      if (mounted.current) {
        setData(value);
        setError(null);
      }
    } catch (caught) {
      if (mounted.current) setError(caught instanceof Error ? caught : new Error(String(caught)));
    } finally {
      inFlight.current = false;
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!visible) return undefined;
    void refresh();
    if (intervalMs === null) return undefined;
    const timer = setInterval(() => void refresh(), intervalMs);
    return () => clearInterval(timer);
  }, [visible, intervalMs, refresh]);

  return { data, error, loading, refresh };
}
