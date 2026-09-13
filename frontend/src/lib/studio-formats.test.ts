import { describe, expect, it } from "vitest";

import { DEFAULT_PERMISSIONS } from "./mission-store";
import { STUDIO_FORMATS, formatUnlocked } from "./studio-formats";

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
});
