"use client";

import { KeyRound } from "lucide-react";

import { useOperatorModels } from "@/components/operator-models-provider";
import { operatorChipClasses } from "@/lib/operator-models";
import { cn } from "@/lib/utils";

export function OperatorModelsChip() {
  const models = useOperatorModels();

  return (
    <button
      type="button"
      suppressHydrationWarning
      onClick={() => models.openSheet()}
      className={cn(
        "font-ui inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
        operatorChipClasses(models.readyText),
      )}
      title={models.readyText ? models.chipLabel : "Paste a model API key"}
    >
      <KeyRound className="size-3.5" />
      {models.chipLabel}
    </button>
  );
}

/** @deprecated use OperatorModelsChip */
export function GeminiKeyChip() {
  return <OperatorModelsChip />;
}
