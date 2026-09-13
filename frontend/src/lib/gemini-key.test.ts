import { describe, expect, it } from "vitest";

import { geminiChipClasses, hasGeminiKey, maskGeminiKey } from "./gemini-key";

describe("maskGeminiKey", () => {
  it("masks to last four", () => {
    expect(maskGeminiKey("AIzaSyDummyKey1234")).toBe("••••1234");
  });

  it("handles empty", () => {
    expect(maskGeminiKey("")).toBe("");
    expect(hasGeminiKey("")).toBe(false);
    expect(hasGeminiKey("short")).toBe(false);
    expect(hasGeminiKey("AIzaSyDummyKey1234")).toBe(true);
  });
});

describe("geminiChipClasses", () => {
  it("pulses until a key is set", () => {
    expect(geminiChipClasses(false)).toContain("animate-pulse");
    expect(geminiChipClasses(true)).not.toContain("animate-pulse");
  });
});
