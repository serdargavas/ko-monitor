import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePolling } from "../src/hooks/usePolling";
import { setHidden } from "./fakes";

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("calls at once and then every interval while visible", async () => {
    const fn = vi.fn().mockResolvedValue("data");
    const { result } = renderHook(() => usePolling(fn, 5000));
    await flush();
    expect(fn).toHaveBeenCalledTimes(1);
    expect(result.current.data).toBe("data");
    await flush(5000);
    expect(fn).toHaveBeenCalledTimes(2);
    await flush(10000);
    expect(fn).toHaveBeenCalledTimes(4);
  });

  it("stops while hidden and refreshes at once when visible again", async () => {
    const fn = vi.fn().mockResolvedValue(1);
    renderHook(() => usePolling(fn, 5000));
    await flush();
    act(() => setHidden(true));
    await flush(30000);
    expect(fn).toHaveBeenCalledTimes(1);
    act(() => setHidden(false));
    await flush();
    expect(fn).toHaveBeenCalledTimes(2);
    await flush(5000);
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("stops calling after unmount", async () => {
    const fn = vi.fn().mockResolvedValue(1);
    const { unmount } = renderHook(() => usePolling(fn, 5000));
    await flush();
    unmount();
    await flush(30000);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("keeps the last data and sets the error on failure, clears it on success", async () => {
    const fn = vi.fn().mockResolvedValueOnce("first").mockRejectedValueOnce(new Error("offline")).mockResolvedValue("again");
    const { result } = renderHook(() => usePolling(fn, 5000));
    await flush();
    await flush(5000);
    expect(result.current.data).toBe("first");
    expect(result.current.error?.message).toBe("offline");
    await flush(5000);
    expect(result.current.data).toBe("again");
    expect(result.current.error).toBeNull();
  });

  it("without an interval loads on mount, on refresh() and when visible again", async () => {
    const fn = vi.fn().mockResolvedValue(1);
    const { result } = renderHook(() => usePolling(fn, null));
    await flush(60000);
    expect(fn).toHaveBeenCalledTimes(1);
    await act(async () => {
      await result.current.refresh();
    });
    expect(fn).toHaveBeenCalledTimes(2);
    act(() => setHidden(true));
    act(() => setHidden(false));
    await flush();
    expect(fn).toHaveBeenCalledTimes(3);
  });
});
