"use client";

import type { CompetitorAccount, CompetitorPost } from "@/lib/types";

export function FindingsGrid({
  posts,
  accounts,
  loading,
}: {
  posts: CompetitorPost[];
  accounts: CompetitorAccount[];
  loading: boolean;
}) {
  const byId = Object.fromEntries(accounts.map((a) => [a.id, a]));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Findings</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Recent rival posts the agent pulled — captions, formats, engagement heat.
        </p>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Loading posts…</p>}

      {!loading && posts.length === 0 && (
        <p className="rounded-lg border border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
          No posts yet. Finish a scout run first.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {posts.map((post) => {
          const account = byId[post.account_id];
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
                  <span className="uppercase text-muted-foreground">{post.format}</span>
                </div>
                <p className="line-clamp-4 text-sm leading-snug">{post.caption}</p>
                <div className="mt-auto flex flex-wrap gap-2 pt-2 text-[11px] text-muted-foreground">
                  <span>{post.likes} likes</span>
                  <span>{post.comments} comments</span>
                  <span>score {post.engagement_score}</span>
                </div>
                {post.themes?.length > 0 && (
                  <p className="text-[11px] text-muted-foreground">
                    {post.themes.slice(0, 4).join(" · ")}
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
