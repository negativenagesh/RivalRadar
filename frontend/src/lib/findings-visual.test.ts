import { describe, expect, it } from "vitest";

import { isVideoVisual } from "./findings-filter";

describe("isVideoVisual", () => {
  it("detects playable video files", () => {
    expect(isVideoVisual("http://gw/ingestion/media/run/post.mp4")).toBe(true);
    expect(isVideoVisual("https://cdn.example/clip.webm?x=1")).toBe(true);
    expect(isVideoVisual("http://gw/ingestion/media/run/post.jpg")).toBe(false);
    expect(isVideoVisual(null)).toBe(false);
  });
});
