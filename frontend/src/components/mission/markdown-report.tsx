"use client";

import type { ReactNode } from "react";

export type MarkdownBlock =
  | { type: "h1" | "h2" | "h3" | "p" | "quote"; text: string }
  | { type: "ul" | "ol"; items: string[] }
  | { type: "hr" };

export function parseMarkdownBlocks(source: string): MarkdownBlock[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let listBuf: { kind: "ul" | "ol"; items: string[] } | null = null;

  const flushList = () => {
    if (listBuf?.items.length) {
      blocks.push({ type: listBuf.kind, items: listBuf.items });
    }
    listBuf = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushList();
      blocks.push({ type: "hr" });
      continue;
    }
    if (trimmed.startsWith("# ")) {
      flushList();
      blocks.push({ type: "h1", text: trimmed.slice(2).trim() });
      continue;
    }
    if (trimmed.startsWith("## ")) {
      flushList();
      blocks.push({ type: "h2", text: trimmed.slice(3).trim() });
      continue;
    }
    if (trimmed.startsWith("### ")) {
      flushList();
      blocks.push({ type: "h3", text: trimmed.slice(4).trim() });
      continue;
    }
    if (trimmed.startsWith("> ")) {
      flushList();
      blocks.push({ type: "quote", text: trimmed.slice(2).trim() });
      continue;
    }
    const ul = trimmed.match(/^[-*]\s+(.+)$/);
    if (ul) {
      if (listBuf?.kind !== "ul") {
        flushList();
        listBuf = { kind: "ul", items: [] };
      }
      listBuf.items.push(ul[1]);
      continue;
    }
    const ol = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (ol) {
      if (listBuf?.kind !== "ol") {
        flushList();
        listBuf = { kind: "ol", items: [] };
      }
      listBuf.items.push(ol[1]);
      continue;
    }
    flushList();
    blocks.push({ type: "p", text: trimmed });
  }
  flushList();
  return blocks;
}

function renderInline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return (
        <em key={i} className="font-accent text-foreground/90">
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={i} className="rounded bg-primary/10 px-1 py-0.5 font-mono text-[0.8em] text-primary">
          {part.slice(1, -1)}
        </code>
      );
    }
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      return (
        <a
          key={i}
          href={link[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
        >
          {link[1]}
        </a>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export function MarkdownReport({
  source,
  className,
}: {
  source: string;
  className?: string;
}) {
  const blocks = parseMarkdownBlocks(source);

  return (
    <article
      className={
        className ??
        "space-y-4 rounded-3xl border border-primary/20 bg-[linear-gradient(180deg,oklch(0.16_0.03_128_/_0.55),oklch(0.12_0_0_/_0.7))] p-6 text-left shadow-[0_0_80px_-24px_oklch(0.87_0.24_128)] backdrop-blur-xl"
      }
    >
      {blocks.map((block, i) => {
        if (block.type === "h1") {
          return (
            <h2 key={i} className="font-shout text-3xl uppercase tracking-tight text-foreground sm:text-4xl">
              {block.text}
            </h2>
          );
        }
        if (block.type === "h2") {
          return (
            <h3
              key={i}
              className="font-ui mt-2 border-t border-primary/20 pt-4 text-[11px] font-bold uppercase tracking-[0.22em] text-primary"
            >
              {block.text}
            </h3>
          );
        }
        if (block.type === "h3") {
          return (
            <h4 key={i} className="font-display text-base font-bold text-foreground">
              {block.text}
            </h4>
          );
        }
        if (block.type === "hr") {
          return <hr key={i} className="border-primary/20" />;
        }
        if (block.type === "quote") {
          return (
            <blockquote
              key={i}
              className="font-accent border-l-2 border-primary/60 pl-4 text-base italic text-muted-foreground"
            >
              {renderInline(block.text)}
            </blockquote>
          );
        }
        if (block.type === "ul" || block.type === "ol") {
          const List = block.type === "ol" ? "ol" : "ul";
          return (
            <List key={i} className={block.type === "ol" ? "space-y-2 pl-5" : "space-y-2 pl-1"}>
              {block.items.map((item, j) => (
                <li
                  key={j}
                  className={
                    block.type === "ol"
                      ? "list-decimal text-sm leading-relaxed text-foreground/90"
                      : "flex gap-3 text-sm leading-relaxed text-foreground/90"
                  }
                >
                  {block.type === "ul" ? (
                    <>
                      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary shadow-[0_0_10px_oklch(0.87_0.24_128)]" />
                      <span>{renderInline(item)}</span>
                    </>
                  ) : (
                    renderInline(item)
                  )}
                </li>
              ))}
            </List>
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
