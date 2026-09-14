"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { pingLlm } from "@/lib/api";
import {
  hasOperatorKey,
  imageModelLabel,
  maskOperatorKey,
  textModelLabel,
  type ImageModel,
  type OperatorState,
  type TextModel,
  type Vendor,
} from "@/lib/operator-models";

type Props = {
  open: boolean;
  onClose: () => void;
  state: OperatorState;
  textModel: TextModel | null;
  imageModel: ImageModel | null;
  setKey: (vendor: Vendor, raw: string) => void;
  setTextModel: (model: TextModel) => void;
  setImageModel: (model: ImageModel) => void;
};

const VENDORS: {
  id: Vendor;
  title: string;
  hint: string;
  placeholder: string;
  docs: string;
}[] = [
  {
    id: "gemini",
    title: "Gemini",
    hint: "Text (3.6 Flash) + Nano Banana 2 images. Required if you want Gemini pixels.",
    placeholder: "AIza…",
    docs: "https://aistudio.google.com/apikey",
  },
  {
    id: "deepseek",
    title: "DeepSeek V4.1 Flash",
    hint: "Model id deepseek-flash. Vision-in / text-out — it cannot paint a PNG.",
    placeholder: "sk-…",
    docs: "https://api-docs.deepseek.com/",
  },
  {
    id: "nvidia",
    title: "NVIDIA (gpt-oss-20b + FLUX)",
    hint: "Free NIM endpoint. gpt-oss-20b writes text; FLUX paints if Gemini is absent.",
    placeholder: "nvapi-…",
    docs: "https://build.nvidia.com/openai/gpt-oss-20b/modelcard",
  },
];

export function OperatorModelsSheet({
  open,
  onClose,
  state,
  textModel,
  imageModel,
  setKey,
  setTextModel,
  setImageModel,
}: Props) {
  const [drafts, setDrafts] = useState<Record<Vendor, string>>({
    gemini: "",
    deepseek: "",
    nvidia: "",
  });
  const [busy, setBusy] = useState<Vendor | null>(null);
  const [status, setStatus] = useState<Record<Vendor, string>>({
    gemini: "",
    deepseek: "",
    nvidia: "",
  });

  if (!open || typeof document === "undefined") return null;

  const geminiLocksImage = hasOperatorKey(state.gemini);

  async function testAndSave(vendor: Vendor) {
    const draft = drafts[vendor].trim();
    if (!draft) return;
    setBusy(vendor);
    setStatus((s) => ({ ...s, [vendor]: "testing…" }));
    try {
      const result = await pingLlm(vendor, draft);
      setKey(vendor, draft);
      setDrafts((d) => ({ ...d, [vendor]: "" }));
      setStatus((s) => ({ ...s, [vendor]: `ok · ${result.model}` }));
    } catch (err) {
      setStatus((s) => ({
        ...s,
        [vendor]: err instanceof Error ? err.message : "Key failed",
      }));
    } finally {
      setBusy(null);
    }
  }

  return createPortal(
    <div
      data-testid="gemini-key-overlay"
      className="fixed inset-0 z-[100] grid place-items-center overflow-y-auto bg-black/70 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative w-full max-w-lg space-y-5 rounded-3xl border border-primary/40 bg-background p-6 shadow-[0_0_80px_-20px_oklch(0.87_0.24_128)]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="operator-models-title"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-ui text-[10px] font-bold uppercase tracking-[0.22em] text-primary">
              operator secrets
            </p>
            <h2 id="operator-models-title" className="font-display mt-1 text-xl font-bold">
              Models
            </h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-1 hover:bg-muted" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <p className="text-sm text-muted-foreground">
          Keys stay in this browser. Test before save. Intel and captions use the text model;
          frames use Nano Banana when a Gemini key exists, otherwise NVIDIA FLUX.
        </p>

        <div className="space-y-4">
          {VENDORS.map((vendor) => {
            const saved = state[vendor.id];
            return (
              <div key={vendor.id} className="space-y-2 rounded-2xl border border-border/60 p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-sm font-semibold">{vendor.title}</p>
                  {hasOperatorKey(saved) ? (
                    <span className="font-mono text-xs text-primary">saved {maskOperatorKey(saved)}</span>
                  ) : (
                    <span className="text-xs text-muted-foreground">empty</span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {vendor.hint}{" "}
                  <a href={vendor.docs} target="_blank" rel="noreferrer" className="text-primary underline">
                    docs
                  </a>
                </p>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <input
                    type="password"
                    autoComplete="off"
                    value={drafts[vendor.id]}
                    onChange={(e) => setDrafts((d) => ({ ...d, [vendor.id]: e.target.value }))}
                    placeholder={vendor.placeholder}
                    className="h-10 w-full rounded-xl border border-border/50 bg-background px-3 font-mono text-sm outline-none focus-visible:border-primary/50"
                  />
                  <Button
                    type="button"
                    disabled={!drafts[vendor.id].trim() || busy !== null}
                    onClick={() => void testAndSave(vendor.id)}
                  >
                    {busy === vendor.id ? "Testing" : "Test & save"}
                  </Button>
                  {hasOperatorKey(saved) && (
                    <Button type="button" variant="outline" onClick={() => setKey(vendor.id, "")}>
                      Clear
                    </Button>
                  )}
                </div>
                {status[vendor.id] && (
                  <p className="text-xs text-muted-foreground">{status[vendor.id]}</p>
                )}
              </div>
            );
          })}
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Text writes with
          </p>
          <div className="flex flex-wrap gap-2">
            {(
              [
                ["gemini", "Gemini 3.6 Flash", hasOperatorKey(state.gemini)],
                ["deepseek", "DeepSeek V4.1 Flash", hasOperatorKey(state.deepseek)],
                ["gptoss", "GPT-OSS 20B", hasOperatorKey(state.nvidia)],
              ] as const
            ).map(([id, label, on]) => (
              <button
                key={id}
                type="button"
                disabled={!on}
                onClick={() => setTextModel(id)}
                className={
                  textModel === id
                    ? "rounded-full border border-primary bg-primary/20 px-3 py-1.5 text-xs font-bold text-primary"
                    : on
                      ? "rounded-full border border-border/60 px-3 py-1.5 text-xs text-muted-foreground hover:border-primary/40"
                      : "cursor-not-allowed rounded-full border border-border/40 px-3 py-1.5 text-xs text-muted-foreground/50"
                }
              >
                {label}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Live: {textModel ? textModelLabel(textModel) : "none — paste a key"}
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Image paints with
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!hasOperatorKey(state.gemini)}
              onClick={() => setImageModel("nano_banana")}
              className={
                imageModel === "nano_banana"
                  ? "rounded-full border border-primary bg-primary/20 px-3 py-1.5 text-xs font-bold text-primary"
                  : "rounded-full border border-border/60 px-3 py-1.5 text-xs text-muted-foreground"
              }
            >
              Nano Banana 2
            </button>
            <button
              type="button"
              disabled={geminiLocksImage || !hasOperatorKey(state.nvidia)}
              onClick={() => setImageModel("nvidia_flux")}
              className={
                !geminiLocksImage && imageModel === "nvidia_flux"
                  ? "rounded-full border border-primary bg-primary/20 px-3 py-1.5 text-xs font-bold text-primary"
                  : "rounded-full border border-border/60 px-3 py-1.5 text-xs text-muted-foreground"
              }
            >
              NVIDIA FLUX
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            {geminiLocksImage
              ? "Gemini key is present — frames always use Nano Banana 2."
              : `Live: ${imageModelLabel(imageModel)}. DeepSeek cannot generate image pixels.`}
          </p>
        </div>
      </div>
    </div>,
    document.body,
  );
}
