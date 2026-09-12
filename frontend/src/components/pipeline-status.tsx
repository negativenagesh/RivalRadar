"use client";

import { motion } from "motion/react";

import type { PipelineRun } from "@/lib/types";

const STATUS_COPY: Record<PipelineRun["status"], string> = {
  pending: "Queued…",
  running: "Generating drafts…",
  done: "Drafts ready",
  error: "Something went wrong",
};

export function PipelineStatus({ run }: { run: PipelineRun }) {
  const busy = run.status === "pending" || run.status === "running";

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-card/40 px-4 py-3">
      {busy ? (
        <motion.span
          className="h-2.5 w-2.5 rounded-full bg-primary"
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
        />
      ) : (
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            run.status === "done" ? "bg-primary" : "bg-chart-2"
          }`}
        />
      )}
      <span className="text-sm font-medium">{STATUS_COPY[run.status]}</span>
      {run.status === "done" && (
        <span className="text-sm text-muted-foreground">
          — {run.draft_ids.length} draft{run.draft_ids.length === 1 ? "" : "s"}
        </span>
      )}
      {run.status === "error" && run.error_detail && (
        <span className="truncate text-sm text-chart-2">{run.error_detail}</span>
      )}
    </div>
  );
}
