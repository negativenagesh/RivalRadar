"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { NavBar } from "@/components/nav-bar";
import { ClusterCard } from "@/components/cluster-card";
import { ThemePills } from "@/components/theme-pills";
import { PipelineStatus } from "@/components/pipeline-status";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePipelineRun } from "@/hooks/use-pipeline-run";
import { generateDigest, generateDrafts, getLatestDigest } from "@/lib/api";
import type { Digest } from "@/lib/types";

export default function DigestPage() {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingDigest, setGeneratingDigest] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { run, track, isRunning } = usePipelineRun();

  useEffect(() => {
    let cancelled = false;
    getLatestDigest()
      .then((latest) => {
        if (!cancelled) {
          setDigest(latest);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setDigest(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleGenerateDigest() {
    setGeneratingDigest(true);
    setError(null);
    try {
      const fresh = await generateDigest();
      setDigest(fresh);
    } catch {
      setError("Couldn't generate a digest — make sure competitor posts have been ingested.");
    } finally {
      setGeneratingDigest(false);
    }
  }

  async function handleGenerateDrafts() {
    setError(null);
    try {
      const { run_id } = await generateDrafts();
      track(run_id);
    } catch {
      setError("Couldn't start draft generation.");
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <NavBar />
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-10 px-6 py-12">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold tracking-tight">This week&apos;s digest</h1>
            <p className="mt-1 text-muted-foreground">
              What competitors are posting, ranked by engagement — and where you have a gap.
            </p>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={handleGenerateDigest} disabled={generatingDigest}>
              {generatingDigest ? "Generating…" : "Refresh digest"}
            </Button>
            <Button onClick={handleGenerateDrafts} disabled={!digest || isRunning}>
              Generate drafts
            </Button>
          </div>
        </div>

        {error && <p className="text-sm text-chart-2">{error}</p>}
        {run && <PipelineStatus run={run} />}
        {run?.status === "done" && (
          <Link href="/review" className="text-sm font-medium text-primary hover:underline">
            View drafts in review →
          </Link>
        )}

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-40 rounded-lg" />
            ))}
          </div>
        ) : !digest ? (
          <div className="rounded-lg border border-dashed border-border/60 py-16 text-center text-muted-foreground">
            No digest yet. Ingest some competitor posts, then hit &ldquo;Refresh digest&rdquo;.
          </div>
        ) : (
          <>
            <section className="grid gap-6 sm:grid-cols-2">
              <div>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  Trending themes
                </h2>
                <ThemePills themes={digest.trending_themes} />
              </div>
              <div>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  Gaps in your own coverage
                </h2>
                <ThemePills themes={digest.gap_themes} variant="gap" />
              </div>
            </section>

            <section>
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Clusters, ranked by engagement
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {digest.clusters.map((cluster, i) => (
                  <ClusterCard key={`${cluster.format}-${cluster.dominant_theme}`} cluster={cluster} index={i} />
                ))}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
