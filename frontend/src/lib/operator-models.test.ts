import { afterEach, describe, expect, it } from "vitest";

import {
  AGNES_KEY_STORAGE,
  DEEPSEEK_KEY_STORAGE,
  IMAGE_MODEL_STORAGE,
  NVIDIA_KEY_STORAGE,
  loadOperatorState,
  resolveImageModel,
  resolveTextModel,
  saveImageModel,
  saveOperatorKey,
} from "./operator-models";
import { GEMINI_KEY_STORAGE } from "./gemini-key";

afterEach(() => {
  window.localStorage.clear();
});

describe("operator model routing", () => {
  it("does not steal Agnes preference when a Gemini key is pasted", () => {
    window.localStorage.setItem(GEMINI_KEY_STORAGE, "AIzaSyDummyKey1234");
    window.localStorage.setItem(NVIDIA_KEY_STORAGE, "nvapi-dummy-key-1234");
    const state = loadOperatorState();
    expect(state.imageModel).toBe("agnes");
    // No browser Agnes key → null so API sends preference "agnes" for server env.
    expect(resolveImageModel(state)).toBeNull();
  });

  it("uses Agnes Image 2.0 Flash when an Agnes key exists", () => {
    window.localStorage.setItem(NVIDIA_KEY_STORAGE, "nvapi-dummy-key-1234");
    window.localStorage.setItem(AGNES_KEY_STORAGE, "sk-agnes-dummy-key-1234");
    const state = loadOperatorState();
    expect(resolveImageModel(state)).toBe("agnes");
  });

  it("keeps Agnes preference when only an NVIDIA key is present", () => {
    window.localStorage.setItem(NVIDIA_KEY_STORAGE, "nvapi-dummy-key-1234");
    const state = loadOperatorState();
    expect(resolveTextModel(state)).toBe("gptoss");
    expect(state.imageModel).toBe("agnes");
    expect(resolveImageModel(state)).toBeNull();
  });

  it("uses Nano Banana only when the operator picks it and has a Gemini key", () => {
    window.localStorage.setItem(GEMINI_KEY_STORAGE, "AIzaSyDummyKey1234");
    window.localStorage.setItem(IMAGE_MODEL_STORAGE, "nano_banana");
    const state = loadOperatorState();
    expect(resolveImageModel(state)).toBe("nano_banana");
  });

  it("uses FLUX when the operator picks it and has an NVIDIA key", () => {
    window.localStorage.setItem(NVIDIA_KEY_STORAGE, "nvapi-dummy-key-1234");
    saveImageModel("nvidia_flux");
    const state = loadOperatorState();
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
