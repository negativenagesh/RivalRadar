"use client";

import type { IntelFacts } from "@/lib/intel-facts";

function barWidth(value: number, max: number): string {
  if (max <= 0) return "4%";
  return `${Math.max(6, Math.round((value / max) * 100))}%`;
}

export function IntelVisuals({ facts }: { facts: IntelFacts }) {
  const heatMax = Math.max(1, ...facts.companies.map((c) => c.avgEngagement));
  const postMax = Math.max(1, ...facts.companies.map((c) => c.posts));
  const cadenceMax = Math.max(
    0.1,
    ...facts.companies.flatMap((c) => c.platforms.map((p) => p.cadencePerDay)),
  );

  return (
    <div className="grid gap-4 text-left lg:grid-cols-2">
      <section className="rounded-3xl border border-border/50 bg-card/40 p-5 backdrop-blur-xl">
        <p className="font-ui text-[10px] font-bold uppercase tracking-[0.22em] text-primary">heat vs the room</p>
        <ul className="mt-4 space-y-4">
          {facts.companies.length ? (
            facts.companies.map((c) => (
              <li key={`${c.role}-${c.name}`}>
                <div className="mb-1 flex items-baseline justify-between gap-2">
                  <span className="font-display text-sm font-bold">
                    {c.name}
                    <span className="ml-2 font-ui text-[10px] uppercase tracking-widest text-muted-foreground">
                      {c.role === "brand" ? "you" : "rival"}
                    </span>
                  </span>
                  <span className="font-shout text-lg text-primary">{c.avgEngagement}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted/60">
                  <div
                    className={
                      c.role === "brand"
                        ? "h-full rounded-full bg-primary shadow-[0_0_16px_oklch(0.87_0.24_128)]"
                        : "h-full rounded-full bg-foreground/45"
                    }
                    style={{ width: barWidth(c.avgEngagement, heatMax) }}
                  />
                </div>
                <p className="mt-1 font-ui text-[10px] uppercase tracking-widest text-muted-foreground">
                  {c.posts}/{postMax} posts in window
                </p>
              </li>
            ))
          ) : (
            <li className="text-sm text-muted-foreground">Zero in-window posts — scout this lookback first.</li>
          )}
        </ul>
      </section>

      <section className="rounded-3xl border border-border/50 bg-card/40 p-5 backdrop-blur-xl">
        <p className="font-ui text-[10px] font-bold uppercase tracking-[0.22em] text-primary">format mix</p>
        <ul className="mt-4 space-y-3">
          {facts.formatMix.length ? (
            facts.formatMix.slice(0, 6).map((row) => (
              <li key={row.format}>
                <div className="mb-1 flex justify-between text-xs">
                  <span className="font-medium">{row.format.replaceAll("_", " ")}</span>
                  <span className="font-ui text-primary">{row.pct}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted/60">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-primary to-primary/40"
                    style={{ width: `${Math.max(6, row.pct)}%` }}
                  />
                </div>
              </li>
            ))
          ) : (
            <li className="text-sm text-muted-foreground">No mix until the scout lands posts.</li>
          )}
        </ul>
      </section>

      <section className="rounded-3xl border border-border/50 bg-card/40 p-5 backdrop-blur-xl lg:col-span-2">
        <p className="font-ui text-[10px] font-bold uppercase tracking-[0.22em] text-primary">cadence radar</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {facts.companies.flatMap((c) =>
            c.platforms.map((p) => (
              <div
                key={`${c.name}-${p.platform}`}
                className="rounded-2xl border border-border/40 bg-background/30 px-4 py-3"
              >
                <p className="font-ui text-[10px] uppercase tracking-widest text-muted-foreground">
                  {c.name} · {p.platform}
                </p>
                <p className="font-shout mt-1 text-2xl text-primary">{p.cadencePerDay}</p>
                <p className="text-xs text-muted-foreground">posts / day · {p.avgLikes}♡ · {p.avgComments}💬</p>
                <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted/60">
                  <div
                    className="h-full rounded-full bg-primary/80"
                    style={{ width: barWidth(p.cadencePerDay, cadenceMax) }}
                  />
                </div>
              </div>
            )),
          )}
          {!facts.companies.length && (
            <p className="text-sm text-muted-foreground">Cadence is a blank tape until posts land.</p>
          )}
        </div>
      </section>
    </div>
  );
}
