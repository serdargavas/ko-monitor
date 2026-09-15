import { describe, expect, it } from "vitest";
import { ApiError, getEvents, getSnapshots, sendTest, streamUrl, subscribe } from "../src/api";
import { stubFetch } from "./fakes";

describe("api", () => {
  it("asks for fresh JSON", async () => {
    const fetchMock = stubFetch({ "/api/events": [] });
    await expect(getEvents(5)).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith("/api/events?limit=5", { cache: "no-store" });
  });

  it("passes the snapshot start as since", async () => {
    const fetchMock = stubFetch({ "/api/snapshots": [] });
    await getSnapshots(1234.5);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/snapshots?since=1234.5");
  });

  it("throws ApiError with the HTTP status", async () => {
    stubFetch({});
    const error = await getEvents().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).message).toBe("/api/events?limit=50: HTTP 404");
  });

  it("posts the subscription as JSON and the test push without a body", async () => {
    const fetchMock = stubFetch({ "/api/push/subscribe": { ok: true }, "/api/push/test": { delivered: true, subscriptions: 1 } });
    const subscription = { endpoint: "https://web.push.apple.com/x", keys: { p256dh: "p", auth: "a" } };
    await subscribe(subscription);
    expect(fetchMock).toHaveBeenCalledWith("/api/push/subscribe", {
      cache: "no-store",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscription),
    });
    await expect(sendTest()).resolves.toEqual({ delivered: true, subscriptions: 1 });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/push/test", { cache: "no-store", method: "POST" });
  });

  it("builds the stream URL from the page address", () => {
    expect(streamUrl(null)).toBe(`ws://${location.host}/api/stream`);
    expect(streamUrl("high")).toBe(`ws://${location.host}/api/stream?quality=high`);
  });
});
