import { useEffect, useRef, useState } from "react";
import { useStream } from "../hooks/useStream";
import { loadQuality, QUALITIES, saveQuality } from "../quality";
import type { Quality } from "../types";

type FullscreenElement = HTMLElement & { webkitRequestFullscreen?: () => void };

function fullscreenSupported(): boolean {
  const proto = HTMLElement.prototype as FullscreenElement;
  return typeof proto.requestFullscreen === "function" || typeof proto.webkitRequestFullscreen === "function";
}

export function Live() {
  const [quality, setQuality] = useState<Quality | null>(loadQuality);
  const [canFullscreen] = useState(fullscreenSupported);
  const { frameUrl, overlay } = useStream(quality, true);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.body.classList.add("live-mode");
    return () => document.body.classList.remove("live-mode");
  }, []);

  const choose = (next: Quality) => {
    if (next === quality) return;
    saveQuality(next);
    setQuality(next);
  };

  const enterFullscreen = () => {
    const stage = stageRef.current as FullscreenElement | null;
    if (!stage) return;
    if (typeof stage.requestFullscreen === "function") stage.requestFullscreen().catch(() => undefined);
    else stage.webkitRequestFullscreen?.();
  };

  return (
    <>
      <div className="live-header">
        <h1>Canlı</h1>
        <div className="quality">
          {QUALITIES.map(([key, text]) => (
            <button
              key={key}
              type="button"
              data-quality={key}
              className={key === quality ? "active" : undefined}
              onClick={() => choose(key)}
            >
              {text}
            </button>
          ))}
          <button type="button" hidden={!canFullscreen} onClick={enterFullscreen}>
            Tam ekran
          </button>
        </div>
      </div>
      <div className="live-stage" ref={stageRef}>
        <img className="live-frame" alt="Canlı oyun görüntüsü" src={frameUrl ?? undefined} />
        <div className="live-overlay" hidden={!overlay}>
          {overlay}
        </div>
      </div>
      <p className="meta">
        {(quality ? "" : "Kalite seçilmedi: bilgisayardaki varsayılan kullanılıyor. ") +
          "Telefonu yan çevirince görüntü tam ekran olur."}
      </p>
    </>
  );
}
