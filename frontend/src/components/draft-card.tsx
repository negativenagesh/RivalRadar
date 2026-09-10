"use client";

import { useState } from "react";
import { motion } from "motion/react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { Draft } from "@/lib/types";

const STATE_LABEL: Record<Draft["review_state"], string> = {
  pending: "Awaiting review",
  edited: "Edited",
  rejected: "Rejected",
  ready_to_publish: "Ready to publish",
};

function stateVariant(state: Draft["review_state"]): "default" | "secondary" | "outline" {
  if (state === "ready_to_publish") return "default";
  if (state === "rejected") return "outline";
  return "secondary";
}

export function DraftCard({
  draft,
  index,
  onApprove,
  onEdit,
  onReject,
}: {
  draft: Draft;
  index: number;
  onApprove: (id: string) => Promise<void>;
  onEdit: (id: string, caption: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draftCaption, setDraftCaption] = useState(draft.final_caption);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  const decided = draft.review_state !== "pending" && draft.review_state !== "edited";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05, ease: "easeOut" }}
    >
      <Card className="border-border/60 bg-card/60">
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="capitalize">
              {draft.cluster_format.replace(/_/g, " ")}
            </Badge>
            <Badge variant={stateVariant(draft.review_state)}>{STATE_LABEL[draft.review_state]}</Badge>
            {!draft.compliance_passed && (
              <Badge variant="outline" className="border-chart-2/60 text-chart-2">
                Compliance flagged
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {editing ? (
            <Textarea
              value={draftCaption}
              onChange={(e) => setDraftCaption(e.target.value)}
              rows={3}
              className="resize-none"
            />
          ) : (
            <p className="text-lg leading-snug">{draft.final_caption}</p>
          )}

          <details className="text-sm text-muted-foreground">
            <summary className="cursor-pointer select-none font-medium text-foreground/80">
              Image concept
            </summary>
            <p className="mt-2 whitespace-pre-wrap">{draft.image_concept}</p>
          </details>

          {!draft.compliance_passed && draft.compliance_llm_reason && (
            <p className="rounded-md border border-chart-2/40 bg-chart-2/10 px-3 py-2 text-sm text-chart-2">
              {draft.compliance_llm_reason}
            </p>
          )}

          {draft.voice_examples_used.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Voice-matched against: {draft.voice_examples_used.join(", ")}
            </p>
          )}
        </CardContent>
        <CardFooter className="flex flex-wrap gap-2">
          {editing ? (
            <>
              <Button
                size="sm"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await onEdit(draft.id, draftCaption);
                    setEditing(false);
                  })
                }
              >
                Save edit
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button size="sm" disabled={busy || decided} onClick={() => run(() => onApprove(draft.id))}>
                Approve
              </Button>
              <Button size="sm" variant="secondary" disabled={busy || decided} onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busy || decided}
                onClick={() => run(() => onReject(draft.id))}
              >
                Reject
              </Button>
            </>
          )}
        </CardFooter>
      </Card>
    </motion.div>
  );
}
