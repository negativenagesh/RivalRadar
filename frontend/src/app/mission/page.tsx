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
  cancelIngestionRun,
  listConnections,
  listIngestionAccounts,
  listIngestionPosts,
  startIngestionRun,
} from "@/lib/api";
import { filterFindingsPosts } from "@/lib/findings-filter";
import {
  DEFAULT_MISSION,
  buildDiscoveryReport,
  buildMissionTargets,
  loadMission,
  missionToIngestionPayload,
  saveMission,
} from "@/lib/mission-store";
import {
  canReachStep,
  focusField,
  type FieldIssue,
  validateConnections,
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
  const [step, setStep] = useState<MissionStep>(0);
  // Same default on server + first client paint; hydrate from localStorage after mount.
  const [mission, setMission] = useState<MissionState>(() => structuredClone(DEFAULT_MISSION));
  const [storageReady, setStorageReady] = useState(false);
  const [starting, setStarting] = useState(false);
  const [killing, setKilling] = useState(false);
  const [scoutError, setScoutError] = useState<string | null>(null);
  const [posts, setPosts] = useState<CompetitorPost[]>([]);
  const [accounts, setAccounts] = useState<CompetitorAccount[]>([]);
  const [loadingPosts, setLoadingPosts] = useState(false);
  const [gateIssue, setGateIssue] = useState<FieldIssue | null>(null);

  const runId = mission.lastRunId ?? null;
  const live = useIngestionLive(runId);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (cancelled) return;
      setMission(loadMission());
      setStorageReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!storageReady) return;
    saveMission(mission);
  }, [mission, storageReady]);

  // Derived: hide the banner as soon as the flagged field is fixed (no setState in effect).
  const gateWarning = useMemo(() => {
    if (!gateIssue) return null;
    const open = [
      ...validateContext(mission),
      ...validateScout(mission, live.run?.status),
      ...validateFindings(posts.length),
    ];
    return open.some((i) => i.fieldId === gateIssue.fieldId) ? gateIssue.message : null;
  }, [gateIssue, mission, posts.length, live.run?.status]);

  const patch = useCallback((partial: Partial<MissionState>) => {
    setMission((prev) => ({ ...prev, ...partial }));
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
    const status = live.run?.status;
    if (status !== "done" && status !== "cancelled" && status !== "error") return;
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (!cancelled) void refreshFindings();
    });
    return () => {
      cancelled = true;
    };
  }, [live.run?.status, refreshFindings]);

  const missionTargets = useMemo(() => buildMissionTargets(mission), [mission]);

  const visiblePosts = useMemo(
    () =>
      filterFindingsPosts(posts, accounts, {
        targets: missionTargets,
        dateFrom: mission.dateFrom,
        dateTo: mission.dateTo,
        lookbackDays: mission.lookbackDays,
      }).map((row) => row.post),
    [posts, accounts, missionTargets, mission.dateFrom, mission.dateTo, mission.lookbackDays],
  );

  const report = useMemo(() => {
    return buildDiscoveryReport({
      brand: mission.brand,
      competitors: mission.competitors,
      posts: visiblePosts,
      permissions: mission.permissions,
      lookbackDays: mission.lookbackDays,
    });
  }, [mission, visiblePosts]);

  const topCaption = visiblePosts[0]?.caption ?? "";

  function applyGate(issues: FieldIssue[]): boolean {
    if (!issues.length) {
      setGateIssue(null);
      return true;
    }
    const first = issues[0];
    setGateIssue(first);
    setStep(first.step);
    window.setTimeout(() => focusField(first.fieldId), 80);
    return false;
  }

  function scrollToTop() {
    window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
  }

  function goToStep(target: MissionStep) {
    if (target === step) return;
    if (target < step) {
      setGateIssue(null);
      setStep(target);
      scrollToTop();
      return;
    }
    const issues = canReachStep(target, mission, visiblePosts.length, live.run?.status);
    if (!applyGate(issues)) return;
    setStep(target);
    scrollToTop();
  }

  function handleContinue() {
    if (step === 0) {
      if (!applyGate(validateContext(mission))) return;
      setStep(1);
      scrollToTop();
      return;
    }
    if (step === 1) {
      if (!applyGate(validateScout(mission, live.run?.status))) return;
      void refreshFindings();
      setStep(2);
      scrollToTop();
      return;
    }
    if (step === 2) {
      if (!applyGate(validateFindings(visiblePosts.length))) return;
      setStep(3);
      scrollToTop();
    }
  }

  async function handleKillScout() {
    if (!runId) return;
    setScoutError(null);
    setKilling(true);
    live.markOptimistic("cancelled", "stopped by operator");
    try {
      await cancelIngestionRun(runId);
      await live.refreshRun();
      await new Promise((resolve) => window.setTimeout(resolve, 900));
      await refreshFindings();
      await live.refreshRun();
    } catch (err) {
      setScoutError(err instanceof Error ? err.message : "Failed to stop scout");
      await live.refreshRun();
    } finally {
      setKilling(false);
    }
  }

  async function handleStartScout() {
    if (!applyGate(validateContext(mission))) {
      setScoutError("Finish Context (brand + rival) before starting scout.");
      return;
    }
    setScoutError(null);
    setStarting(true);
    try {
      const connections = await listConnections();
      if (!applyGate(validateConnections(missionTargets, connections))) {
        setScoutError(
          "Connect every Context platform (except YouTube) before starting scout.",
        );
        return;
      }

      if (runId && (live.run?.status === "running" || live.run?.status === "pending")) {
        live.markOptimistic("cancelled", "stopped by operator");
        try {
          await cancelIngestionRun(runId);
        } catch {
          // Still allow a fresh start if cancel races a finished run.
        }
      }

      const body = missionToIngestionPayload(mission);
      const created = await startIngestionRun(body);
      live.primeRun(created.run_id, created.status === "running" ? "running" : "pending");
      patch({ lastRunId: created.run_id });
      setGateIssue(null);
    } catch (err) {
      setScoutError(err instanceof Error ? err.message : "Failed to start scout");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,oklch(0.87_0.24_128_/_0.07),transparent_55%)]" />
      <NavBar />
      <MissionProgress step={step} onStepClick={goToStep} />

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
        <div className="mb-10 text-center">
          <p className="font-ui text-xs font-semibold uppercase tracking-[0.28em] text-primary">
            Operator console
          </p>
          <h1 className="font-shout text-jumble-wild mt-3 text-5xl uppercase sm:text-6xl">
            Mission <span className="text-primary">Control</span>
          </h1>
          <p className="font-accent mx-auto mt-4 max-w-2xl text-base italic text-muted-foreground sm:text-lg">
            Feed the agent your brand + rivals, watch the live scout hop every platform, review
            findings, then unlock what it can create.
          </p>
        </div>

        {gateWarning && (
          <div
            role="alert"
            className="mb-6 animate-in fade-in slide-in-from-top-2 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-sm text-destructive"
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
              lookbackDays={mission.lookbackDays}
              onLookbackChange={(lookbackDays) => patch({ lookbackDays })}
              dateFrom={mission.dateFrom}
              dateTo={mission.dateTo}
              onCustomRangeChange={(dateFrom, dateTo) => patch({ dateFrom, dateTo })}
              targets={missionTargets}
              onStart={() => void handleStartScout()}
              onKill={() => void handleKillScout()}
              starting={starting}
              killing={killing}
              runId={runId}
              connected={live.connected}
              events={live.events}
              frames={live.frames}
              latestScreenshot={live.latestScreenshot}
              run={live.run}
              error={scoutError}
            />
          </div>
        )}

        {step === 2 && (
          <div id="findings-grid">
            <FindingsGrid
              posts={posts}
              accounts={accounts}
              targets={missionTargets}
              loading={loadingPosts}
              lookbackDays={mission.lookbackDays}
              dateFrom={mission.dateFrom}
              dateTo={mission.dateTo}
            />
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
            className="font-display h-14 gap-3 px-8 text-base font-semibold"
          >
            <ArrowLeft className="size-5" />
            Back
          </Button>
          <div className="flex flex-wrap justify-center gap-3">
            {step === 2 && (
              <Button variant="secondary" className="font-display h-14 px-6" onClick={() => void refreshFindings()}>
                Refresh posts
              </Button>
            )}
            {step < 3 ? (
              <Button
                onClick={handleContinue}
                className="font-display h-14 gap-3 px-10 text-base font-semibold shadow-[0_0_36px_-8px_oklch(0.87_0.24_128)]"
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
