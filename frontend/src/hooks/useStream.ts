import { useEffect, useRef, useState } from "react";
import { streamUrl } from "../api";
import type { Quality } from "../types";
import { useVisibility } from "./useVisibility";

export const RECONNECT_MS = [1000, 2000, 5000, 10000];
// The server closes with 1008 for a foreign Origin or an unknown quality: retrying cannot help.
export const POLICY_VIOLATION = 1008;

const STATUS_TEXT: Record<string, string> = {
  minimized: "Oyun penceresi küçültülmüş, görüntü alınamıyor",
  not_found: "Oyun penceresi bulunamadı",
  black: "Ekran siyah",
};

/** Text message of WS /api/stream ({"status": ...}) → overlay text. */
export function statusText(message: string): string {
  let status = "";
  try {
    status = String((JSON.parse(message) as { status?: unknown }).status ?? "");
  } catch {
    status = "";
  }
  return STATUS_TEXT[status] || "Görüntü bekleniyor…";
}

export interface StreamView {
  /** Object URL of the newest JPEG frame. */
  frameUrl: string | null;
  /** Text over the picture; "" hides the overlay. */
  overlay: string;
}

/**
 * One WebSocket to /api/stream while enabled and visible. Reconnects after a drop with a bounded
 * backoff, reconnects once when quality changes, closes when hidden/disabled/unmounted.
 */
export function useStream(quality: Quality | null, enabled: boolean): StreamView {
  const visible = useVisibility();
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [overlay, setOverlay] = useState("Bağlanıyor…");
  const frameRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !visible) {
      setOverlay("Duraklatıldı");
      return undefined;
    }
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let stopped = false;

    const showFrame = (blob: Blob) => {
      const previous = frameRef.current;
      const url = URL.createObjectURL(blob);
      frameRef.current = url;
      setFrameUrl(url);
      if (previous) URL.revokeObjectURL(previous);
    };

    const connect = () => {
      retryTimer = undefined;
      if (stopped) return;
      setOverlay(attempts ? "Yeniden bağlanıyor…" : "Bağlanıyor…");
      const ws = new WebSocket(streamUrl(quality));
      ws.binaryType = "blob";
      socket = ws;
      ws.onmessage = (event: MessageEvent) => {
        if (socket !== ws) return;
        if (typeof event.data === "string") {
          setOverlay(statusText(event.data));
          return;
        }
        attempts = 0;
        setOverlay("");
        showFrame(event.data as Blob);
      };
      ws.onclose = (event: CloseEvent) => {
        if (socket !== ws) return; // closed on purpose: quality change, page hidden or screen left
        socket = null;
        if (stopped) return;
        if (event.code === POLICY_VIOLATION) {
          setOverlay(`Sunucu bağlantıyı reddetti (${event.reason || "1008"}). Sayfayı yenileyip tekrar dene.`);
          return;
        }
        const delay = RECONNECT_MS[Math.min(attempts, RECONNECT_MS.length - 1)];
        attempts += 1;
        setOverlay(`Bağlantı koptu, ${Math.round(delay / 1000)} sn içinde yeniden denenecek…`);
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      const ws = socket;
      socket = null;
      ws?.close(); // the server stops capturing and encoding for this viewer
    };
  }, [quality, enabled, visible]);

  useEffect(
    () => () => {
      if (frameRef.current) URL.revokeObjectURL(frameRef.current);
      frameRef.current = null;
    },
    [],
  );

  return { frameUrl, overlay };
}
