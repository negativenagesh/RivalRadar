"use client";

/** Lightweight markdown renderer for discovery reports (no extra deps). */
export function MarkdownReport({ source }: { source: string }) {
  const blocks = parseBlocks(source);

  return (
    <article className="space-y-4 rounded-3xl border border-border/50 bg-card/40 p-6 backdrop-blur-xl">
      {blocks.map((block, i) => {
        if (block.type === "h1") {
          return (
            <h2 key={i} className="text-2xl font-bold tracking-tight text-foreground">
              {block.text}
            </h2>
          );
        }
        if (block.type === "h2") {
          return (
            <h3
              key={i}
              className="mt-2 border-t border-border/40 pt-4 text-sm font-semibold uppercase tracking-[0.16em] text-primary"
            >
              {block.text}
            </h3>
          );
        }
        if (block.type === "ul") {
          return (
            <ul key={i} className="space-y-2 pl-1">
              {block.items.map((item, j) => (
                <li key={j} className="flex gap-2 text-sm leading-relaxed text-muted-foreground">
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" />
                  <span className="text-foreground/90">{renderInline(item)}</span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="text-sm leading-relaxed text-muted-foreground">
            {renderInline(block.text)}
          </p>
        );
      })}
    </article>
  );
}

type Block =
  | { type: "h1" | "h2" | "p"; text: string }
  | { type: "ul"; items: string[] };

function parseBlocks(source: string): Block[] {
  const lines = source.split("\n");
  const blocks: Block[] = [];
  let listBuf: string[] = [];

  const flushList = () => {
    if (listBuf.length) {
      blocks.push({ type: "ul", items: listBuf });
      listBuf = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushList();
      continue;
    }
    if (line.startsWith("# ")) {
      flushList();
      blocks.push({ type: "h1", text: line.slice(2).trim() });
      continue;
    }
    if (line.startsWith("## ")) {
      flushList();
      blocks.push({ type: "h2", text: line.slice(3).trim() });
      continue;
    }
    if (line.startsWith("- ")) {
      listBuf.push(line.slice(2).trim());
      continue;
    }
    flushList();
    blocks.push({ type: "p", text: line.trim() });
  }
  flushList();
  return blocks;
}

function renderInline(text: string): React.ReactNode {
  // very light **bold** support
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part}</span>;
  });
}
