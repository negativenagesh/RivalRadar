"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { NavBar } from "@/components/nav-bar";
import { BrandForm } from "@/components/mission/brand-form";
import { DiscoveryReport } from "@/components/mission/discovery-report";
import { FindingsGrid } from "@/components/mission/findings-grid";
import { LiveScout } from "@/components/mission/live-scout";
import {
  MissionProgress,
  type MissionStep,
} from "@/components/mission/mission-progress";
import { Button } from "@/components/ui/button";
import { useIngestionLive } from "@/hooks/use-ingestion-live";
import {
  listIngestionAccounts,
  listIngestionPosts,
  startIngestionRun,
} from "@/lib/api";
import {
  buildDiscoveryReport,
  loadMission,
  missionToIngestionPayload,
  saveMission,
} from "@/lib/mission-store";
import {
  canReachStep,
  focusField,
  type FieldIssue,
  validateContext,
  validateFindings,
  validateScout,
} from "@/lib/mission-validate";
import type {
  BrandProfile,
  CompetitorAccount,
  CompetitorPost,
  CompetitorProfile,
  CreativePermissions,
  MissionState,
} from "@/lib/types";

export default function MissionPage() {
  const [hydrated, setHydrated] = useState(false);
  const [step, setStep] = useState<MissionStep>(0);
  const [mission, setMission] = useState<MissionState | null>(null);
  const [starting, setStarting] = useState(false);
  const [scoutError, setScoutError] = useState<string | null>(null);
  const [posts, setPosts] = useState<CompetitorPost[]>([]);
  const [accounts, setAccounts] = useState<CompetitorAccount[]>([]);
  const [loadingPosts, setLoadingPosts] = useState(false);
  const [gateWarning, setGateWarning] = useState<string | null>(null);
  const [gateFieldId, setGateFieldId] = useState<string | null>(null);

  const runId = mission?.lastRunId ?? null;
  const live = useIngestionLive(runId);

  useEffect(() => {
    setMission(loadMission());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!mission || !hydrated) return;
    saveMission(mission);
  }, [mission, hydrated]);

  // Clear the banner as soon as the flagged field is fixed.
  useEffect(() => {
    if (!mission || !gateWarning) return;
    const open = [
      ...validateContext(mission),
      ...validateScout(mission),
      ...validateFindings(posts.length),
    ];
    const stillBroken = gateFieldId
      ? open.some((i) => i.fieldId === gateFieldId)
      : open.some((i) => i.message === gateWarning);
    if (!stillBroken) {
      setGateWarning(null);
      setGateFieldId(null);
    }
  }, [mission, posts.length, gateWarning, gateFieldId]);

  const patch = useCallback((partial: Partial<MissionState>) => {
    setMission((prev) => (prev ? { ...prev, ...partial } : prev));
  }, []);

  const setBrand = useCallback((brand: BrandProfile) => patch({ brand }), [patch]);
  const setCompetitors = useCallback(
    (competitors: CompetitorProfile[]) => patch({ competitors }),
    [patch],
  );
  const setPermissions = useCallback(
    (permissions: CreativePermissions) => patch({ permissions }),
    [patch],
  );

  const refreshFindings = useCallback(async () => {
    setLoadingPosts(true);
    try {
      const [p, a] = await Promise.all([listIngestionPosts(), listIngestionAccounts()]);
      setPosts(p);
      setAccounts(a);
    } catch {
      setPosts([]);
      setAccounts([]);
    } finally {
      setLoadingPosts(false);
    }
  }, []);

  useEffect(() => {
    if (live.done && live.run?.status === "done") {
      void refreshFindings();
    }
  }, [live.done, live.run?.status, refreshFindings]);

  const report = useMemo(() => {
    if (!mission) return "";
    return buildDiscoveryReport({
      brand: mission.brand,
      competitors: mission.competitors,
      posts,
      permissions: mission.permissions,
    });
  }, [mission, posts]);

  const topCaption = posts[0]?.caption ?? "";

  function applyGate(issues: FieldIssue[]): boolean {
    if (!issues.length) {
      setGateWarning(null);
      setGateFieldId(null);
      return true;
    }
    const first = issues[0];
    setGateWarning(first.message);
    setGateFieldId(first.fieldId);
    setStep(first.step);
    window.setTimeout(() => focusField(first.fieldId), 80);
    return false;
  }

  function goToStep(target: MissionStep) {
    if (!mission) return;
    if (target === step) return;
    if (target < step) {
      setGateWarning(null);
      setGateFieldId(null);
      setStep(target);
      return;
    }
    const issues = canReachStep(target, mission, posts.length);
    if (!applyGate(issues)) return;
    setStep(target);
  }

  function handleContinue() {
    if (!mission) return;
    if (step === 0) {
      if (!applyGate(validateContext(mission))) return;
      setStep(1);
      return;
    }
    if (step === 1) {
      if (!applyGate(validateScout(mission))) return;
      void refreshFindings();
      setStep(2);
      return;
    }
    if (step === 2) {
      if (!applyGate(validateFindings(posts.length))) return;
      setStep(3);
    }
  }

  async function handleStartScout() {
    if (!mission) return;
    if (!applyGate(validateContext(mission))) return;
    setScoutError(null);
    setStarting(true);
    try {
      const body = missionToIngestionPayload(mission);
      const created = await startIngestionRun(body);
      patch({ lastRunId: created.run_id });
      setGateWarning(null);
      setGateFieldId(null);
    } catch (err) {
      setScoutError(err instanceof Error ? err.message : "Failed to start scout");
    } finally {
      setStarting(false);
    }
  }

  if (!hydrated || !mission) {
    return (
      <div className="flex min-h-screen flex-col">
        <NavBar />
        <p className="p-10 text-sm text-muted-foreground">Loading mission…</p>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,oklch(0.87_0.24_128_/_0.07),transparent_55%)]" />
      <NavBar />
      <MissionProgress step={step} onStepClick={goToStep} />

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">
            Operator console
          </p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight sm:text-5xl">
            Mission <span className="text-primary">Control</span>
          </h1>
          <p className="mt-3 max-w-xl text-sm text-muted-foreground sm:text-base">
            Feed the agent your brand + rivals, watch the live scout, review findings, then unlock
            what it can create.
          </p>
        </div>

        {gateWarning && (
          <div
            role="alert"
            className="mb-6 animate-in fade-in slide-in-from-top-2 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            {gateWarning}
          </div>
        )}

        {step === 0 && (
          <BrandForm
            brand={mission.brand}
            competitors={mission.competitors}
            onBrandChange={setBrand}
            onCompetitorsChange={setCompetitors}
          />
        )}

        {step === 1 && (
          <div id="scout-start">
            <LiveScout
              recordSession={mission.recordSession}
              onRecordChange={(recordSession) => patch({ recordSession })}
              onStart={() => void handleStartScout()}
              starting={starting}
              runId={runId}
              connected={live.connected}
              events={live.events}
              latestScreenshot={live.latestScreenshot}
              run={live.run}
              error={scoutError}
            />
          </div>
        )}

        {step === 2 && (
          <div id="findings-grid">
            <FindingsGrid posts={posts} accounts={accounts} loading={loadingPosts} />
          </div>
        )}

        {step === 3 && (
          <DiscoveryReport
            report={report}
            permissions={mission.permissions}
            onPermissionsChange={setPermissions}
            brandName={mission.brand.displayName}
            voiceNotes={mission.brand.voiceNotes}
            competitorCaption={topCaption}
          />
        )}

        <div className="mt-14 flex flex-col gap-4 border-t border-border/50 pt-8 sm:flex-row sm:items-center sm:justify-between">
          <Button
            variant="outline"
            disabled={step === 0}
            onClick={() => goToStep((step - 1) as MissionStep)}
            className="h-14 gap-3 px-8 text-base font-semibold"
          >
            <ArrowLeft className="size-5" />
            Back
          </Button>
          <div className="flex flex-wrap gap-3">
            {step === 2 && (
              <Button variant="secondary" className="h-14 px-6" onClick={() => void refreshFindings()}>
                Refresh posts
              </Button>
            )}
            {step < 3 ? (
              <Button
                onClick={handleContinue}
                className="h-14 gap-3 px-10 text-base font-semibold shadow-[0_0_36px_-8px_oklch(0.87_0.24_128)]"
              >
                Continue
                <ArrowRight className="size-5" />
              </Button>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
