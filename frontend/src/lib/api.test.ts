import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveDraft,
  generateCreative,
  generateDigest,
  getLatestDigest,
  listDrafts,
} from "./api";
import { GEMINI_KEY_STORAGE } from "./gemini-key";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("api client", () => {
  it("getLatestDigest hits /digest/latest", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "d1", clusters: [], trending_themes: [], gap_themes: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const digest = await getLatestDigest();
    expect(digest.id).toBe("d1");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/digest\/latest$/),
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("generateDigest POSTs /digest/generate", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "d2", clusters: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await generateDigest();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/digest\/generate$/),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listDrafts and approveDraft use the review endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id: "draft-1" }],
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "draft-1", review_state: "ready_to_publish" }),
      });
    vi.stubGlobal("fetch", fetchMock);

    const drafts = await listDrafts();
    expect(drafts).toHaveLength(1);

    await approveDraft("draft-1");
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringMatching(/\/drafts\/draft-1\/approve$/),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("throws when the gateway returns a non-OK status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "down" }),
      }),
    );

    await expect(getLatestDigest()).rejects.toThrow(/down/);
  });

  it("surfaces Failed to fetch as a gateway unreachable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(getLatestDigest()).rejects.toThrow(/Gateway unreachable/);
  });

  it("sends X-Gemini-Key only on Mission LLM routes", async () => {
    window.localStorage.setItem(GEMINI_KEY_STORAGE, "AIzaSyDummyKey1234");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ kind: "studio", text: "caption" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await generateCreative({ kind: "studio", brand_name: "Pixis" });
    expect(fetchMock.mock.calls[0][1].headers["X-Gemini-Key"]).toBe("AIzaSyDummyKey1234");
    expect(fetchMock.mock.calls[0][1].headers["X-Text-Model"]).toBe("gemini");
    expect(fetchMock.mock.calls[0][1].headers["X-Image-Model"]).toBe("nano_banana");

    fetchMock.mockClear();
    fetchMock.mockResolvedValue({ ok: true, json: async () => [] });
    await listDrafts();
    expect(fetchMock.mock.calls[0][1].headers["X-Gemini-Key"]).toBeUndefined();
  });
});
