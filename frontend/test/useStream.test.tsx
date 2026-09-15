import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useStream } from "../src/hooks/useStream";
import type { Quality } from "../src/types";
import { FakeWebSocket, installStreamFakes, setHidden } from "./fakes";

describe("useStream", () => {
  let urls: ReturnType<typeof installStreamFakes>;

  beforeEach(() => {
    vi.useFakeTimers();
    urls = installStreamFakes();
  });

  it("opens exactly one blob socket to the stream URL", () => {
    const { result, rerender } = renderHook(() => useStream("low", true));
    rerender();
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream?quality=low`);
    expect(FakeWebSocket.last().binaryType).toBe("blob");
    expect(result.current.overlay).toBe("Bağlanıyor…");
  });

  it("shows frames and revokes the previous object URL", () => {
    const { result, unmount } = renderHook(() => useStream(null, true));
    const ws = FakeWebSocket.last();
    act(() => ws.receive(new Blob(["a"])));
    expect(result.current).toEqual({ frameUrl: "blob:frame-1", overlay: "" });
    act(() => ws.receive(new Blob(["b"])));
    expect(result.current.frameUrl).toBe("blob:frame-2");
    expect(urls.revokeObjectURL).toHaveBeenCalledWith("blob:frame-1");
    unmount();
    expect(urls.revokeObjectURL).toHaveBeenLastCalledWith("blob:frame-2");
    expect(ws.closed).toBe(true);
  });

  it("turns status messages into Turkish overlay text", () => {
    const { result } = renderHook(() => useStream(null, true));
    act(() => FakeWebSocket.last().receive('{"status":"minimized"}'));
    expect(result.current.overlay).toBe("Oyun penceresi küçültülmüş, görüntü alınamıyor");
    act(() => FakeWebSocket.last().receive("not json"));
    expect(result.current.overlay).toBe("Görüntü bekleniyor…");
  });

  it("reconnects once when the quality changes", () => {
    const { rerender } = renderHook(({ quality }: { quality: Quality }) => useStream(quality, true), {
      initialProps: { quality: "low" },
    });
    const first = FakeWebSocket.last();
    rerender({ quality: "high" });
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(first.closed).toBe(true);
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream?quality=high`);
    act(() => first.serverClose(1005)); // the late close event of the old socket is ignored
    rerender({ quality: "high" });
    act(() => vi.advanceTimersByTime(30000));
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("closes while hidden and reconnects when visible again", () => {
    const { result } = renderHook(() => useStream(null, true));
    act(() => setHidden(true));
    expect(FakeWebSocket.last().closed).toBe(true);
    expect(result.current.overlay).toBe("Duraklatıldı");
    act(() => vi.advanceTimersByTime(30000));
    expect(FakeWebSocket.instances).toHaveLength(1);
    act(() => setHidden(false));
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(result.current.overlay).toBe("Bağlanıyor…");
  });

  it("backs off 1, 2, 5 and at most 10 seconds", () => {
    const { result } = renderHook(() => useStream(null, true));
    [1000, 2000, 5000, 10000, 10000].forEach((delay, index) => {
      act(() => FakeWebSocket.instances[index].serverClose(1006));
      expect(result.current.overlay).toBe(`Bağlantı koptu, ${delay / 1000} sn içinde yeniden denenecek…`);
      act(() => vi.advanceTimersByTime(delay - 1));
      expect(FakeWebSocket.instances).toHaveLength(index + 1);
      act(() => vi.advanceTimersByTime(1));
      expect(FakeWebSocket.instances).toHaveLength(index + 2);
      expect(result.current.overlay).toBe("Yeniden bağlanıyor…");
    });
  });

  it("does not retry after close code 1008", () => {
    const { result } = renderHook(() => useStream("high", true));
    act(() => FakeWebSocket.last().serverClose(1008, "origin not allowed"));
    expect(result.current.overlay).toBe("Sunucu bağlantıyı reddetti (origin not allowed). Sayfayı yenileyip tekrar dene.");
    act(() => vi.advanceTimersByTime(60000));
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("clears a pending retry on unmount", () => {
    const { unmount } = renderHook(() => useStream(null, true));
    act(() => FakeWebSocket.last().serverClose(1006));
    unmount();
    act(() => vi.advanceTimersByTime(30000));
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("stays closed while disabled", () => {
    const { result } = renderHook(() => useStream(null, false));
    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(result.current.overlay).toBe("Duraklatıldı");
  });
});
