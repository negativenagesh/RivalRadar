import type { CompetitorPost } from "./types";

/**
 * Posts already in the DB when a scout session starts should not appear in the
 * Live Scout "In-window posts" grid. New extractions (ids not in the baseline)
 * stream in as refreshFindings / live frames update.
 *
 * `baselineIds === null` means no active session filter (show everything).
 */
export function postsForActiveScoutSession(
  posts: CompetitorPost[],
  baselineIds: ReadonlySet<string> | null,
): CompetitorPost[] {
  if (!baselineIds) return posts;
  return posts.filter((p) => !baselineIds.has(p.id));
}

/** Snapshot ids present before Start Scout — used as the hide-list for this session. */
export function scoutBaselineFromPosts(posts: CompetitorPost[]): Set<string> {
  return new Set(posts.map((p) => p.id));
}
