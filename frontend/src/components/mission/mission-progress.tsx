"use client";

import { cn } from "@/lib/utils";

const STEPS = ["Context", "Scout", "Findings", "Report"] as const;

export type MissionStep = 0 | 1 | 2 | 3;

export function MissionProgress({
  step,
  onStepClick,
}: {
  step: MissionStep;
  onStepClick: (target: MissionStep) => void;
}) {
  return (
    <div className="sticky top-[53px] z-40 border-b border-border/50 bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center gap-2 px-6 py-3">
        {STEPS.map((label, i) => {
          const active = i === step;
          const done = i < step;
          return (
            <div key={label} className="flex flex-1 items-center gap-2">
              <button
                type="button"
                onClick={() => onStepClick(i as MissionStep)}
                className={cn(
                  "flex items-center gap-2 rounded-full px-1 py-0.5 text-left transition-all duration-300",
                  "hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
                  !active && "opacity-70 hover:opacity-100",
                )}
              >
                <span
                  className={cn(
                    "flex size-8 shrink-0 items-center justify-center rounded-full font-mono text-xs font-bold transition-all duration-300",
                    active &&
                      "bg-primary text-primary-foreground shadow-[0_0_20px_-4px_oklch(0.87_0.24_128)] scale-110",
                    done && !active && "bg-primary/20 text-primary",
                    !active && !done && "bg-muted text-muted-foreground",
                  )}
                >
                  {i + 1}
                </span>
                <span
                  className={cn(
                    "hidden text-sm sm:inline",
                    active ? "font-semibold text-foreground" : "text-muted-foreground",
                  )}
                >
                  {label}
                </span>
              </button>
              {i < STEPS.length - 1 && (
                <div
                  className={cn("mx-1 h-px flex-1", done ? "bg-primary/50" : "bg-border")}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
