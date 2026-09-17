import { afterEach, describe, expect, it } from "vitest";

import {
  appendStudioAssets,
  clearStudioAssets,
  readStudioAssets,
  removeStudioAsset,
  studioAssetsKey,
} from "./studio-assets";
import type { CreativeResult } from "./types";

afterEach(() => {
  clearStudioAssets("Pixis");
  window.localStorage.clear();
});

function frame(text: string): CreativeResult {
  return {
    kind: "studio",
    text,
    image_concept: "concept",
    image_mime_type: "image/png",
    image_data_base64: "aaa",
    overlay_text: "hi",
  };
}

describe("studio asset library", () => {
  it("appends assets across generates and survives re-read", () => {
    appendStudioAssets("Pixis", [frame("one")], { format: "meme", platform: "instagram" });
    appendStudioAssets("Pixis", [frame("two")], { format: "myth_bust", platform: "linkedin" });
    const rows = readStudioAssets("Pixis");
    expect(rows).toHaveLength(2);
    expect(rows[0].text).toBe("one");
    expect(rows[1].text).toBe("two");
    expect(rows[1].format).toBe("myth_bust");
    expect(window.localStorage.getItem(studioAssetsKey("Pixis"))).toBeTruthy();
  });

  it("removes a single asset by id", () => {
    const rows = appendStudioAssets("Pixis", [frame("keep"), frame("drop")], {
      format: "hot_take",
      platform: "x",
    });
    const next = removeStudioAsset("Pixis", rows[1].id);
    expect(next).toHaveLength(1);
    expect(next[0].text).toBe("keep");
  });
});
