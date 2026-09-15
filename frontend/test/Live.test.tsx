import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { QUALITY_STORAGE_KEY } from "../src/quality";
import { Live } from "../src/screens/Live";
import { FakeWebSocket, installStreamFakes } from "./fakes";

describe("Live screen", () => {
  beforeEach(() => {
    installStreamFakes();
  });

  it("connects, shows the server status and then frames", () => {
    const { container, unmount } = render(<Live />);
    expect(screen.getByText("Bağlanıyor…")).toBeTruthy();
    expect(document.body.classList.contains("live-mode")).toBe(true);
    expect(
      screen.getByText(
        "Kalite seçilmedi: bilgisayardaki varsayılan kullanılıyor. Telefonu yan çevirince görüntü tam ekran olur.",
      ),
    ).toBeTruthy();
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream`);

    act(() => FakeWebSocket.last().receive('{"status":"not_found"}'));
    expect(screen.getByText("Oyun penceresi bulunamadı")).toBeTruthy();

    act(() => FakeWebSocket.last().receive(new Blob(["jpeg"])));
    expect(screen.getByAltText("Canlı oyun görüntüsü").getAttribute("src")).toBe("blob:frame-1");
    expect((container.querySelector(".live-overlay") as HTMLElement).hidden).toBe(true);

    unmount();
    expect(document.body.classList.contains("live-mode")).toBe(false);
  });

  it("remembers the chosen quality and reconnects once", () => {
    render(<Live />);
    const high = screen.getByRole("button", { name: "Yüksek" });
    fireEvent.click(high);
    expect(localStorage.getItem(QUALITY_STORAGE_KEY)).toBe("high");
    expect(high.className).toBe("active");
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[0].closed).toBe(true);
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream?quality=high`);
    fireEvent.click(high);
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(screen.getByText("Telefonu yan çevirince görüntü tam ekran olur.")).toBeTruthy();
  });

  it("starts with the saved quality", () => {
    localStorage.setItem(QUALITY_STORAGE_KEY, "low");
    render(<Live />);
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream?quality=low`);
    expect(screen.getByRole("button", { name: "Düşük" }).className).toBe("active");
  });
});
