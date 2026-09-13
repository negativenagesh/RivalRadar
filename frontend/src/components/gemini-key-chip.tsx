"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { KeyRound, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useGeminiKey } from "@/components/gemini-key-provider";
import { geminiChipClasses } from "@/lib/gemini-key";
import { cn } from "@/lib/utils";

export function GeminiKeyModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const gemini = useGeminiKey();
  const [draft, setDraft] = useState("");

  if (!open || typeof document === "undefined") return null;

  // Portal to <body>. The chip lives in a sticky navbar with backdrop-blur,
  // which creates a containing block so `position:fixed` would pin to the
  // header and shoot the sheet off the top of the viewport.
  return createPortal(
    <div
      data-testid="gemini-key-overlay"
      className="fixed inset-0 z-[100] grid place-items-center overflow-y-auto bg-black/70 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative w-full max-w-md space-y-4 rounded-3xl border border-primary/40 bg-background p-6 shadow-[0_0_80px_-20px_oklch(0.87_0.24_128)]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="gemini-key-title"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-ui text-[10px] font-bold uppercase tracking-[0.22em] text-primary">
              operator secret
            </p>
            <h2 id="gemini-key-title" className="font-display mt-1 text-xl font-bold">
              Gemini API key
            </h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-1 hover:bg-muted" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <p className="text-sm text-muted-foreground">
          This key lives in <span className="font-mono text-xs">your browser</span> only. Mission intel,
          memes, and sniper comments use it — never the server .env.
        </p>
        {gemini.ready ? (
          <p className="rounded-2xl border border-primary/30 bg-primary/10 px-3 py-2 font-mono text-sm text-primary">
            saved {gemini.masked}
          </p>
        ) : (
          <p className="rounded-2xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            No key yet — Report / studio / sniper stay locked until you paste one.
          </p>
        )}
        <label className="block space-y-1.5">
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Paste key
          </span>
          <input
            type="password"
            autoComplete="off"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="AIza…"
            className="h-11 w-full rounded-xl border border-border/50 bg-background px-3.5 font-mono text-sm outline-none focus-visible:border-primary/50"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => {
              gemini.setKey(draft);
              setDraft("");
              onClose();
            }}
            disabled={!draft.trim()}
          >
            Save key
          </Button>
          {gemini.ready && (
            <Button
              variant="outline"
              onClick={() => {
                gemini.clear();
                setDraft("");
              }}
            >
              Clear
            </Button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function GeminiKeyChip() {
  const gemini = useGeminiKey();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        suppressHydrationWarning
        onClick={() => setOpen(true)}
        className={cn(
          "font-ui inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
          geminiChipClasses(gemini.ready),
        )}
        title={gemini.ready ? `Gemini ${gemini.masked}` : "Paste Gemini API key"}
      >
        <KeyRound className="size-3.5" />
        {gemini.ready ? `Gemini ${gemini.masked}` : "Gemini"}
      </button>
      <GeminiKeyModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
