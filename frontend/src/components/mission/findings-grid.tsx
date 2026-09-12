"use client";

import type { CompetitorAccount, CompetitorPost } from "@/lib/types";

function sourceFromThemes(themes: string[]): string {
  const hit = themes.find((t) => t.startsWith("source:"));
  if (!hit) return "scout";
  return hit.replace("source:", "").replace(/_/g, " ");
}

function viewsFromThemes(themes: string[]): number | null {
  const hit = themes.find((t) => t.startsWith("views:"));
  if (!hit) return null;
  const n = Number(hit.replace("views:", ""));
  return Number.isFinite(n) ? n : null;
}

function relativeDate(iso: string): string {
  return iso.slice(0, 10) || iso;
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
  const filtered = posts;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Findings</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Posts from the last {lookbackDays} days — captions, formats, engagement heat, and
          YouTube stats when the agent pulled channel uploads.
        </p>
      </div>

      {accounts.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {accounts.map((a) => (
            <div
              key={a.id}
              className="rounded-xl border border-border/60 bg-card/40 px-3 py-2 text-xs"
            >
              <span className="font-semibold text-primary">{a.display_name}</span>
              <span className="text-muted-foreground">
                {" "}
                · {a.handle} · {a.platform}
              </span>
            </div>
          ))}
        </div>
      )}

      {loading && <p className="text-sm text-muted-foreground">Loading posts…</p>}

      {!loading && filtered.length === 0 && (
        <p className="rounded-lg border border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
          No posts yet. Finish a scout run first — or widen lookback if the window was empty.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((post) => {
          const account = byId[post.account_id];
          const source = sourceFromThemes(post.themes ?? []);
          const views = viewsFromThemes(post.themes ?? []);
          const isYt = account?.platform === "youtube" || (post.themes ?? []).includes("youtube");
          const watchUrl =
            isYt && post.external_post_id
              ? `https://www.youtube.com/watch?v=${post.external_post_id}`
              : null;
          const title = post.caption.split("\n")[0] ?? post.caption;

          return (
            <article
              key={post.id}
              className="flex flex-col overflow-hidden rounded-xl border border-border/60 bg-card/40 transition hover:border-primary/40"
            >
              <div className="aspect-[4/3] bg-muted/30">
                {post.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={post.image_url}
                    alt=""
                    className="h-full w-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center font-mono text-xs text-muted-foreground">
                    {post.format}
                  </div>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-2 p-4">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-medium text-primary">
                    {account?.handle ?? post.account_id.slice(0, 8)}
                  </span>
                  <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] uppercase text-primary">
                    {source}
                  </span>
                </div>
                <p className="line-clamp-3 text-sm font-medium leading-snug">{title}</p>
                {post.caption.includes("\n") && (
                  <p className="line-clamp-2 text-xs text-muted-foreground">
                    {post.caption.split("\n").slice(1).join(" ").trim()}
                  </p>
                )}
                <div className="mt-auto flex flex-wrap gap-2 pt-2 text-[11px] text-muted-foreground">
                  <span>{post.likes} likes</span>
                  <span>{post.comments} comments</span>
                  {views !== null ? <span>{views.toLocaleString()} views</span> : null}
                  <span>score {post.engagement_score}</span>
                  <span>{relativeDate(post.posted_at)}</span>
                </div>
                {watchUrl && (
                  <a
                    href={watchUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Open on YouTube
                  </a>
                )}
                {post.themes?.length > 0 && (
                  <p className="text-[11px] text-muted-foreground">
                    {post.themes
                      .filter((t) => !t.startsWith("source:") && !t.startsWith("views:"))
                      .slice(0, 4)
                      .join(" · ")}
                  </p>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
