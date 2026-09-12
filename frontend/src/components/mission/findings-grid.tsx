"use client";

import { useMemo } from "react";

import type { CompetitorAccount, CompetitorPost } from "@/lib/types";

function sourceFromThemes(themes: string[]): string {
  const hit = themes.find((t) => t.startsWith("source:"));
  if (!hit) return "scout";
  return hit.replace("source:", "").replace(/_/g, " ");
}

function linkFromThemes(themes: string[]): string | null {
  const hit = themes.find((t) => t.startsWith("link:"));
  return hit ? hit.replace("link:", "") : null;
}

function viewsFromThemes(themes: string[]): number | null {
  const hit = themes.find((t) => t.startsWith("views:"));
  if (!hit) return null;
  const n = Number(hit.replace("views:", ""));
  return Number.isFinite(n) ? n : null;
}

function resolveImage(url: string | null, gateway?: string): string | null {
  if (!url) return null;
  if (url.startsWith("http") || url.startsWith("data:")) return url;
  const base = gateway || process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${url.startsWith("/") ? url : `/${url}`}`;
}

export function FindingsGrid({
  posts,
  accounts,
  loading,
  lookbackDays,
}: {
  posts: CompetitorPost[];
  accounts: CompetitorAccount[];
  loading: boolean;
  lookbackDays: number;
}) {
  const byId = Object.fromEntries(accounts.map((a) => [a.id, a]));

  const byPlatform = useMemo(() => {
    const map = new Map<string, CompetitorPost[]>();
    for (const post of posts) {
      const account = byId[post.account_id];
      const platform =
        account?.platform ||
        post.themes?.find((t) =>
          ["youtube", "linkedin", "instagram", "tiktok", "x", "threads", "mock"].includes(t),
        ) ||
        "other";
      const list = map.get(platform) ?? [];
      list.push(post);
      map.set(platform, list);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [posts, byId]);

  return (
    <div className="mx-auto max-w-6xl space-y-10 text-center">
      <div className="space-y-3">
        <p className="font-ui text-xs font-semibold uppercase tracking-[0.28em] text-primary">
          intel dump
        </p>
        <h2 className="font-shout text-jumble-wild text-4xl uppercase sm:text-5xl">Findings</h2>
        <p className="font-accent mx-auto max-w-2xl text-base italic text-muted-foreground">
          Platform-wise tiles from the last {lookbackDays} days — captions, shots, heat, deep links.
        </p>
      </div>

      {accounts.length > 0 && (
        <div className="flex flex-wrap justify-center gap-2">
          {accounts.map((a) => (
            <div
              key={a.id}
              className="rounded-2xl border border-border/60 bg-card/40 px-3 py-2 text-left text-xs"
            >
              <span className="font-display font-semibold text-primary">{a.display_name}</span>
              <span className="font-ui text-muted-foreground">
                {" "}
                · {a.handle} · {a.platform}
              </span>
            </div>
          ))}
        </div>
      )}

      {loading && <p className="font-ui text-sm text-muted-foreground">Loading posts…</p>}

      {!loading && posts.length === 0 && (
        <p className="rounded-2xl border border-border/60 px-4 py-10 font-accent text-sm italic text-muted-foreground">
          No posts yet. Finish a multi-platform scout first.
        </p>
      )}

      {byPlatform.map(([platform, platformPosts], idx) => (
        <section key={platform} className={`space-y-4 ${idx % 2 === 0 ? "tilt-l" : "tilt-r"}`}>
          <h3 className="font-shout text-3xl uppercase text-primary">{platform}</h3>
          <div className="grid gap-4 text-left sm:grid-cols-2 lg:grid-cols-3">
            {platformPosts.map((post) => {
              const account = byId[post.account_id];
              const source = sourceFromThemes(post.themes ?? []);
              const views = viewsFromThemes(post.themes ?? []);
              const external = linkFromThemes(post.themes ?? []);
              const isYt =
                platform === "youtube" || (post.themes ?? []).includes("youtube");
              const watchUrl =
                isYt && post.external_post_id && !post.external_post_id.startsWith("web-")
                  ? `https://www.youtube.com/watch?v=${post.external_post_id}`
                  : external;
              const img = resolveImage(post.image_url);
              const title = post.caption.split("\n")[0] ?? post.caption;

              return (
                <article
                  key={post.id}
                  className="flex flex-col overflow-hidden rounded-3xl border border-border/60 bg-card/40 transition hover:border-primary/50 hover:shadow-[0_0_40px_-18px_oklch(0.87_0.24_128)]"
                >
                  <div className="aspect-[4/3] bg-muted/30">
                    {img ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={img}
                        alt=""
                        className="h-full w-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    ) : (
                      <div className="font-ui flex h-full items-center justify-center text-xs uppercase text-muted-foreground">
                        {post.format}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-1 flex-col gap-2 p-4">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-display font-medium text-primary">
                        {account?.handle ?? post.account_id.slice(0, 8)}
                      </span>
                      <span className="font-ui rounded-full bg-primary/15 px-2 py-0.5 text-[10px] uppercase text-primary">
                        {source}
                      </span>
                    </div>
                    <p className="font-display line-clamp-3 text-sm font-semibold leading-snug">
                      {title}
                    </p>
                    {post.caption.includes("\n") && (
                      <p className="font-accent line-clamp-2 text-xs italic text-muted-foreground">
                        {post.caption.split("\n").slice(1).join(" ").trim()}
                      </p>
                    )}
                    <div className="font-ui mt-auto flex flex-wrap gap-2 pt-2 text-[11px] text-muted-foreground">
                      <span>{post.likes} likes</span>
                      <span>{post.comments} comments</span>
                      {views !== null ? <span>{views.toLocaleString()} views</span> : null}
                      <span>score {post.engagement_score}</span>
                      <span>{post.posted_at.slice(0, 10)}</span>
                    </div>
                    {watchUrl && (
                      <a
                        href={watchUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-ui text-xs font-bold text-primary hover:underline"
                      >
                        Open original →
                      </a>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
