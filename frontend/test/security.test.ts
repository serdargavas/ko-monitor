import { describe, expect, it } from "vitest";
import indexHtml from "../index.html?raw";

const sources = import.meta.glob("../src/**/*.{ts,tsx,css}", { query: "?raw", import: "default", eager: true }) as Record<
  string,
  string
>;

describe("security", () => {
  it("scans every source file", () => {
    expect(Object.keys(sources)).toContain("../src/App.tsx");
  });

  it("never renders raw HTML", () => {
    for (const [path, text] of Object.entries(sources)) {
      expect(text, path).not.toMatch(/dangerouslySetInnerHTML|innerHTML/);
    }
  });

  it("loads nothing from another host (no CDN)", () => {
    for (const [path, text] of Object.entries({ ...sources, "index.html": indexHtml })) {
      expect(text, path).not.toMatch(/https?:\/\//);
    }
  });
});
