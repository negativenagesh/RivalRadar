"use client";

import { useMemo, useState } from "react";

import type { CompetitorAccount, CompetitorPost } from "@/lib/types";
import { ingestionMediaUrl } from "@/lib/api";

function linkFromThemes(themes: string[]): string | null {
  const hit = themes.find((t) => t.startsWith("link:"));
  return hit ? hit.replace("link:", "") : null;
}

function resolveImage(post: CompetitorPost): string | null {
  const key = post.media_keys?.[0];
  if (key) return ingestionMediaUrl(key);
  const url = post.image_url || post.media_urls?.[0] || null;
  if (!url) return null;
  if (url.startsWith("http") || url.startsWith("data:")) return url;
  const base = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${url.startsWith("/") ? url : `/${url}`}`;
}

function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

function watchUrl(post: CompetitorPost, platform: string): string | null {
  const external = linkFromThemes(post.themes ?? []);
  const isYt = platform === "youtube" || (post.themes ?? []).includes("youtube");
  if (isYt && post.external_post_id && !post.external_post_id.startsWith("web-")) {
    return `https://www.youtube.com/watch?v=${post.external_post_id}`;
  }
  return external;
}

type Group = {
  company: string;
  platform: string;
  day: string;
  posts: CompetitorPost[];
};

export function FindingsGrid({
  posts,
  accounts,
  loading,
  lookbackDays,
  dateFrom,
  dateTo,
}: {
  posts: CompetitorPost[];
  accounts: CompetitorAccount[];
  loading: boolean;
  lookbackDays: number;
  dateFrom?: string | null;
  dateTo?: string | null;
}) {
  const byId = Object.fromEntries(accounts.map((a) => [a.id, a]));
  const [openComments, setOpenComments] = useState<string | null>(null);

  const groups = useMemo(() => {
    const map = new Map<string, Group>();
    for (const post of posts) {
      const account = byId[post.account_id];
      const platform =
        account?.platform ||
        post.themes?.find((t) =>
          ["youtube", "linkedin", "instagram", "tiktok", "x", "threads", "mock"].includes(t),
        ) ||
        "other";
      const company = account?.display_name || account?.handle || "Unknown";
      const day = dayKey(post.posted_at);
      const key = `${company}||${platform}||${day}`;
      const g = map.get(key) ?? { company, platform, day, posts: [] };
      g.posts.push(post);
      map.set(key, g);
    }
    return [...map.values()].sort((a, b) => {
      const c = a.company.localeCompare(b.company);
      if (c) return c;
      const p = a.platform.localeCompare(b.platform);
      if (p) return p;
      return b.day.localeCompare(a.day);
    });
  }, [posts, byId]);

  const windowLabel =
    dateFrom && dateTo ? `${dateFrom} → ${dateTo}` : `last ${lookbackDays} days`;

  return (
    <div className="mx-auto max-w-6xl space-y-10 text-center">
      <div className="space-y-3">
        <p className="font-ui text-xs font-semibold uppercase tracking-[0.28em] text-primary">
          intel dump
        </p>
        <h2 className="font-shout text-jumble-wild text-4xl uppercase sm:text-5xl">Findings</h2>
        <p className="font-accent mx-auto max-w-2xl text-base italic text-muted-foreground">
          Company → platform → day · media, captions, heat, top comments · {windowLabel}
        </p>
      </div>

      {loading && <p className="font-ui text-sm text-muted-foreground">Loading posts…</p>}

      {!loading && posts.length === 0 && (
        <div className="space-y-2 rounded-2xl border border-border/60 px-4 py-10">
          <p className="font-accent text-sm italic text-muted-foreground">
            No posts in this window.
          </p>
          <p className="font-ui text-xs text-muted-foreground">
            Widen date range · Reconnect Instagram · Confirm YouTube API / yt-dlp
          </p>
        </div>
      )}

      {groups.map((group) => (
        <section key={`${group.company}-${group.platform}-${group.day}`} className="space-y-4 text-left">
          <div className="flex flex-wrap items-baseline justify-center gap-2 text-center sm:justify-start">
            <h3 className="font-display text-2xl font-bold">{group.company}</h3>
            <span className="font-ui text-xs uppercase tracking-widest text-primary">
              {group.platform}
            </span>
            <span className="font-ui text-xs text-muted-foreground">{group.day}</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {group.posts.map((post) => {
              const img = resolveImage(post);
              const title = post.caption.split("\n")[0] ?? post.caption;
              const views = post.views ?? null;
              const href = watchUrl(post, group.platform);
              const comments = post.comment_sample ?? [];
              const open = openComments === post.id;

              return (
                <article
                  key={post.id}
                  className="flex flex-col overflow-hidden rounded-3xl border border-border/60 bg-card/40"
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
                    <p className="font-display line-clamp-3 text-sm font-semibold leading-snug">
                      {title}
                    </p>
                    <div className="font-ui flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                      <span>{post.likes} likes</span>
                      <span>{post.comments} comments</span>
                      {views !== null && views !== undefined ? (
                        <span>{Number(views).toLocaleString()} views</span>
                      ) : null}
                      {post.shares ? <span>{post.shares} shares</span> : null}
                    </div>
                    {href && (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-ui text-xs font-bold text-primary hover:underline"
                      >
                        Open original →
                      </a>
                    )}
                    {comments.length > 0 && (
                      <div className="mt-1 border-t border-border/40 pt-2">
                        <button
                          type="button"
                          className="font-ui text-[11px] font-semibold uppercase tracking-wide text-primary"
                          onClick={() => setOpenComments(open ? null : post.id)}
                        >
                          {open ? "Hide" : "Top comments"} ({Math.min(10, comments.length)})
                        </button>
                        {open && (
                          <ul className="mt-2 max-h-48 space-y-2 overflow-y-auto">
                            {comments.slice(0, 10).map((c, i) => (
                              <li key={`${post.id}-c-${i}`} className="rounded-xl bg-background/50 px-2 py-1.5">
                                <p className="font-display text-[11px] font-semibold text-primary">
                                  {c.author}
                                  <span className="ml-2 font-ui font-normal text-muted-foreground">
                                    {c.likes} likes
                                  </span>
                                </p>
                                <p className="font-accent text-xs italic text-muted-foreground">
                                  {c.text}
                                </p>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
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
