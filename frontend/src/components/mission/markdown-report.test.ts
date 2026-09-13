import { describe, expect, it } from "vitest";

import { parseMarkdownBlocks } from "./markdown-report";

describe("parseMarkdownBlocks", () => {
  it("parses headings, bullets, numbered lists, quotes, and links", () => {
    const blocks = parseMarkdownBlocks(
      [
        "# Intel brief",
        "",
        "## Plays",
        "- **Cadence** is 0.7/day",
        "1. Lean into memes",
        "2. Sniper the [permalink](https://x.com/a)",
        "",
        "> numbers first",
        "### Receipts",
        "plain paragraph",
      ].join("\n"),
    );
    expect(blocks[0]).toEqual({ type: "h1", text: "Intel brief" });
    expect(blocks[1]).toEqual({ type: "h2", text: "Plays" });
    expect(blocks[2]).toEqual({ type: "ul", items: ["**Cadence** is 0.7/day"] });
    expect(blocks[3]).toEqual({ type: "ol", items: ["Lean into memes", "Sniper the [permalink](https://x.com/a)"] });
    expect(blocks[4]).toEqual({ type: "quote", text: "numbers first" });
    expect(blocks[5]).toEqual({ type: "h3", text: "Receipts" });
    expect(blocks[6]).toEqual({ type: "p", text: "plain paragraph" });
  });
});
