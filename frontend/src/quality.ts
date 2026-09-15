import type { Quality } from "./types";

export const QUALITIES: ReadonlyArray<readonly [Quality, string]> = [
  ["low", "Düşük"],
  ["medium", "Orta"],
  ["high", "Yüksek"],
];
export const QUALITY_STORAGE_KEY = "ko-monitor.quality";

/** The quality chosen earlier on this phone; null → the server's [api] stream_quality. */
export function loadQuality(): Quality | null {
  try {
    const saved = localStorage.getItem(QUALITY_STORAGE_KEY);
    return QUALITIES.find(([key]) => key === saved)?.[0] ?? null;
  } catch {
    return null; // storage unavailable: use the server default
  }
}

export function saveQuality(quality: Quality): void {
  try {
    localStorage.setItem(QUALITY_STORAGE_KEY, quality);
  } catch {
    // storage unavailable: the choice lasts until the screen is left
  }
}
