"use client";

import { useEffect, useState } from "react";

import { NavBar } from "@/components/nav-bar";
import { DraftCard } from "@/components/draft-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { approveDraft, editDraft, listDrafts, rejectDraft } from "@/lib/api";
import type { Draft } from "@/lib/types";

export default function ReviewPage() {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listDrafts()
      .then((result) => {
        if (!cancelled) setDrafts(result);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRefresh() {
    setLoading(true);
    try {
      setDrafts(await listDrafts());
    } finally {
      setLoading(false);
    }
  }

  function updateDraft(updated: Draft) {
    setDrafts((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
  }

  return (
    <div className="flex min-h-screen flex-col">
      <NavBar />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-12">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold tracking-tight">Review queue</h1>
            <p className="mt-1 text-muted-foreground">
              Every draft is here, compliance flag and all — you decide what ships.
            </p>
          </div>
          <Button variant="secondary" onClick={handleRefresh}>
            Refresh
          </Button>
        </div>

        {loading ? (
          <div className="flex flex-col gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-56 rounded-lg" />
            ))}
          </div>
        ) : drafts.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border/60 py-16 text-center text-muted-foreground">
            No drafts yet. Generate some from the digest page.
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {drafts.map((draft, i) => (
              <DraftCard
                key={draft.id}
                draft={draft}
                index={i}
                onApprove={async (id) => updateDraft(await approveDraft(id))}
                onEdit={async (id, caption) => updateDraft(await editDraft(id, caption))}
                onReject={async (id) => updateDraft(await rejectDraft(id))}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
