"use client";

import { useMemo, useState, type ReactNode } from "react";
import { ExternalLink, Heart, MessageCircle, Eye, Repeat2 } from "lucide-react";

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
  // Never treat Live Scout screenshot paths as Findings media
  if (url.includes("/screenshots/")) return null;
  if (url.startsWith("http") || url.startsWith("data:")) return url;
  const base = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${url.startsWith("/") ? url : `/${url}`}`;
}

function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

function watchUrl(post: CompetitorPost, platform: string): string | null {
  const external = linkFromThemes(post.themes ?? []);
  if (external) return external;
  const id = post.external_post_id || "";
  if (platform === "youtube" && id && !id.startsWith("web-") && !id.includes(":")) {
    return `https://www.youtube.com/watch?v=${id}`;
  }
  if (id.startsWith("instagram:")) {
    const code = id.slice("instagram:".length);
    return `https://www.instagram.com/p/${code}/`;
  }
  if (id.startsWith("tiktok:")) {
    return `https://www.tiktok.com/video/${id.slice("tiktok:".length)}`;
  }
  if (id.startsWith("x:")) {
    return `https://x.com/i/status/${id.slice("x:".length)}`;
  }
  return null;
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, "")}k`;
  return String(n);
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
    for (const g of map.values()) {
      g.posts.sort((a, b) => (b.likes + b.comments) - (a.likes + a.comments));
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
    <div className="relative mx-auto max-w-6xl space-y-12">
      <div className="pointer-events-none absolute inset-x-0 -top-8 -z-10 h-64 bg-[radial-gradient(ellipse_at_top,oklch(0.87_0.24_128_/_0.14),transparent_60%)]" />

      <header className="space-y-3 text-center">
        <p className="font-ui text-xs font-semibold uppercase tracking-[0.28em] text-primary">
          intel dump
        </p>
        <h2 className="font-shout text-jumble-wild text-4xl uppercase sm:text-6xl">Findings</h2>
        <p className="font-accent mx-auto max-w-2xl text-base italic text-muted-foreground">
          Real post media · heat under every drop · {windowLabel}
        </p>
      </header>

      {loading && (
        <p className="font-ui animate-pulse text-center text-sm text-muted-foreground">
          Pulling post media…
        </p>
      )}

      {!loading && posts.length === 0 && (
        <div className="mx-auto max-w-lg space-y-2 rounded-[2rem] border border-border/50 bg-card/20 px-6 py-12 text-center">
          <p className="font-display text-xl font-bold">No posts in this window</p>
          <p className="font-accent text-sm italic text-muted-foreground">
            Connect Instagram → widen dates → re-run scout. Screenshots stay in Live Scout; Findings
            only shows downloaded post media.
          </p>
        </div>
      )}

      {groups.map((group) => (
        <section
          key={`${group.company}-${group.platform}-${group.day}`}
          className="space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-500"
        >
          <div className="flex flex-wrap items-end gap-3 border-b border-border/40 pb-3">
            <h3 className="font-display text-3xl font-bold tracking-tight">{group.company}</h3>
            <span className="font-ui mb-1 rounded-full bg-primary/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] text-primary">
              {group.platform}
            </span>
            <span className="font-accent mb-1 text-sm italic text-muted-foreground">{group.day}</span>
            <span className="font-ui mb-1 ml-auto text-[11px] text-muted-foreground">
              {group.posts.length} posts
            </span>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {group.posts.map((post) => {
              const img = resolveImage(post);
              const title = (post.caption.split("\n")[0] ?? post.caption).trim() || "Untitled drop";
              const views = post.views ?? 0;
              const href = watchUrl(post, group.platform);
              const comments = post.comment_sample ?? [];
              const open = openComments === post.id;

              return (
                <article
                  key={post.id}
                  className="group flex flex-col overflow-hidden rounded-[1.75rem] border border-border/50 bg-gradient-to-b from-card/50 to-card/20 transition duration-300 hover:-translate-y-1 hover:border-primary/40 hover:shadow-[0_20px_60px_-30px_oklch(0.87_0.24_128_/_0.55)]"
                >
                  <div className="relative aspect-[4/5] overflow-hidden bg-[radial-gradient(circle_at_30%_20%,oklch(0.87_0.24_128_/_0.12),transparent_55%)]">
                    {img ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={img}
                        alt=""
                        className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    ) : (
                      <div className="font-shout flex h-full items-center justify-center text-2xl uppercase tracking-widest text-muted-foreground/40">
                        {post.format}
                      </div>
                    )}
                  </div>

                  {/* Metrics live directly under the media — the heat strip */}
                  <div className="grid grid-cols-4 gap-px border-y border-border/40 bg-border/30">
                    <Metric cell label="likes" value={post.likes} icon={<Heart className="size-3" />} />
                    <Metric
                      cell
                      label="comments"
                      value={post.comments}
                      icon={<MessageCircle className="size-3" />}
                    />
                    <Metric cell label="views" value={views} icon={<Eye className="size-3" />} />
                    <Metric
                      cell
                      label="shares"
                      value={post.shares}
                      icon={<Repeat2 className="size-3" />}
                    />
                  </div>

                  <div className="flex flex-1 flex-col gap-3 p-4">
                    <p className="font-display line-clamp-3 text-[15px] font-semibold leading-snug">
                      {title}
                    </p>
                    {href && (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-ui inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-primary transition hover:gap-2"
                      >
                        Open original
                        <ExternalLink className="size-3" aria-hidden />
                      </a>
                    )}
                    {comments.length > 0 && (
                      <div className="border-t border-border/40 pt-2">
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
                              <li
                                key={`${post.id}-c-${i}`}
                                className="rounded-2xl bg-background/60 px-3 py-2"
                              >
                                <p className="font-display text-[11px] font-semibold text-primary">
                                  {c.author}
                                  <span className="ml-2 font-ui font-normal text-muted-foreground">
                                    {fmt(c.likes)} likes
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

function Metric({
  label,
  value,
  icon,
  cell,
}: {
  label: string;
  value: number;
  icon: ReactNode;
  cell?: boolean;
}) {
  return (
    <div
      className={
        cell
          ? "flex flex-col items-center gap-0.5 bg-background/80 px-1 py-2.5"
          : "flex items-center gap-1"
      }
    >
      <span className="text-primary/80">{icon}</span>
      <span className="font-shout text-sm leading-none tracking-tight">{fmt(value)}</span>
      <span className="font-ui text-[9px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
    </div>
  );
}
