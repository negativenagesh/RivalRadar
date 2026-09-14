import { afterEach, describe, expect, it } from "vitest";

import {
  DEEPSEEK_KEY_STORAGE,
  NVIDIA_KEY_STORAGE,
  loadOperatorState,
  resolveImageModel,
  resolveTextModel,
  saveOperatorKey,
} from "./operator-models";
import { GEMINI_KEY_STORAGE } from "./gemini-key";

afterEach(() => {
  window.localStorage.clear();
});

describe("operator model routing", () => {
  it("prefers Gemini pixels whenever a Gemini key exists", () => {
    window.localStorage.setItem(GEMINI_KEY_STORAGE, "AIzaSyDummyKey1234");
    window.localStorage.setItem(NVIDIA_KEY_STORAGE, "nvapi-dummy-key-1234");
    const state = loadOperatorState();
    expect(resolveImageModel(state)).toBe("nano_banana");
  });

  it("uses FLUX when only an NVIDIA key is present", () => {
    window.localStorage.setItem(NVIDIA_KEY_STORAGE, "nvapi-dummy-key-1234");
    const state = loadOperatorState();
    expect(resolveTextModel(state)).toBe("gptoss");
    expect(resolveImageModel(state)).toBe("nvidia_flux");
  });

  it("DeepSeek can write text but cannot paint", () => {
    saveOperatorKey("deepseek", "sk-dummy-key-1234");
    const state = loadOperatorState();
    expect(resolveTextModel(state)).toBe("deepseek");
    expect(resolveImageModel(state)).toBeNull();
    expect(window.localStorage.getItem(DEEPSEEK_KEY_STORAGE)).toContain("sk-");
  });
});
