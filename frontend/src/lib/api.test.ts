import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveDraft,
  generateDigest,
  getLatestDigest,
  listDrafts,
} from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
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
});
