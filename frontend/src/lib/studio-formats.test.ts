import { describe, expect, it } from "vitest";

import { DEFAULT_PERMISSIONS } from "./mission-store";
import { STUDIO_FORMATS, formatLabel, formatUnlocked } from "./studio-formats";

describe("studio formats", () => {
  it("covers the war-room chip grid", () => {
    expect(STUDIO_FORMATS.map((f) => f.id)).toEqual(
      expect.arrayContaining([
        "meme",
        "founder_2am",
        "receipt_carousel",
        "myth_bust",
        "trend_jack",
        "comparison",
        "x_thread",
      ]),
    );
  });

  it("gates unused permission chips", () => {
    const locked = { ...DEFAULT_PERMISSIONS, carouselOutlines: false, comparisonSlides: false };
    expect(formatUnlocked("receipt_carousel", locked)).toBe(false);
    expect(formatUnlocked("hot_take", locked)).toBe(true);
    expect(formatUnlocked("comparison", { ...locked, comparisonSlides: true })).toBe(true);
  });

  it("resolves human labels for loading copy and card headers", () => {
    expect(formatLabel("product_story")).toBe("Product flex + human story");
    expect(formatLabel("meme")).toBe("Shitpost / meme");
    expect(formatLabel("unknown_format")).toBe("unknown_format");
  });
});
