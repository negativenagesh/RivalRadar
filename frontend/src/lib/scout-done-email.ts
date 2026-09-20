/** Plain + HTML summaries for scout-done marketer email (from IntelFacts). */

import type { IntelFacts } from "@/lib/intel-facts";

export type ScoutDoneEmailContent = {
  /** Short line for the in-app notification bell. */
  shortBody: string;
  /** Full plain-text body for email / a11y. */
  emailBody: string;
  /** HTML body for Resend. */
  emailHtml: string;
};

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmtNum(n: number): string {
  if (!Number.isFinite(n)) return "0";
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 10) / 10);
}

/** Build marketer-facing scout-done copy from the same facts War Room uses. */
export function formatScoutDoneEmail(facts: IntelFacts): ScoutDoneEmailContent {
  const brand = facts.companies.find((c) => c.role === "brand");
  const rivals = facts.companies.filter((c) => c.role === "rival");
  const totalPosts = facts.companies.reduce((n, c) => n + c.posts, 0);
  const brandPosts = brand?.posts ?? 0;
  const rivalPosts = rivals.reduce((n, c) => n + c.posts, 0);

  const shortBody = `${totalPosts} posts in ${facts.window.label} · brand ${brandPosts} / rivals ${rivalPosts}. Full metrics emailed — open Findings → War Room.`;

  const lines: string[] = [];
  lines.push(`Window: ${facts.window.label} (${facts.window.days} days)`);
  lines.push(`Posts in window: ${totalPosts} (your brand ${brandPosts} · rivals ${rivalPosts})`);
  lines.push("");

  for (const co of facts.companies) {
    const tag = co.role === "brand" ? "YOUR BRAND" : "RIVAL";
    lines.push(`${co.name} [${tag}]`);
    lines.push(
      `  Posts ${co.posts} · avg engagement ${fmtNum(co.avgEngagement)} · visual ${co.visualPct}%`,
    );
    for (const p of co.platforms) {
      lines.push(
        `  ${p.platform}: ${p.posts} posts · avg ${fmtNum(p.avgLikes)} likes / ${fmtNum(p.avgComments)} comments / ${fmtNum(p.avgShares)} shares` +
          (p.avgViews > 0 ? ` / ${fmtNum(p.avgViews)} views` : "") +
          ` · cadence ${fmtNum(p.cadencePerDay)}/day · comment rate ${fmtNum(p.commentRate)}%`,
      );
    }
    lines.push("");
  }

  if (facts.formatMix.length) {
    lines.push("Format mix");
    lines.push(
      "  " +
        facts.formatMix
          .slice(0, 6)
          .map((f) => `${f.format} ${f.pct}% (${f.count})`)
          .join(" · "),
    );
    lines.push("");
  }

  if (facts.topThemes.length) {
    lines.push("Top themes");
    lines.push(
      "  " + facts.topThemes.slice(0, 6).map((t) => `${t.theme} (${t.count})`).join(" · "),
    );
    lines.push("");
  }

  if (facts.topPosts.length) {
    lines.push("Top posts by engagement");
    facts.topPosts.slice(0, 5).forEach((p, i) => {
      const hook = (p.caption || "").replace(/\s+/g, " ").trim().slice(0, 100);
      lines.push(
        `  ${i + 1}. [${p.company} · ${p.platform}] ${hook}${hook.length >= 100 ? "…" : ""}`,
      );
      lines.push(
        `     ${p.likes} likes · ${p.comments} comments · ${p.shares} shares` +
          (p.views > 0 ? ` · ${p.views} views` : "") +
          ` · score ${fmtNum(p.score)} · ${p.format}`,
      );
    });
    lines.push("");
  }

  if (facts.winningBecause.length) {
    lines.push("What's working");
    for (const s of facts.winningBecause.slice(0, 4)) lines.push(`  • ${s}`);
    lines.push("");
  }
  if (facts.leakingBecause.length) {
    lines.push("Watch / fix");
    for (const s of facts.leakingBecause.slice(0, 4)) lines.push(`  • ${s}`);
    lines.push("");
  }

  lines.push("Next: Findings → War Room for the full brief and counter-moves.");
  const emailBody = lines.join("\n").trim();

  const companyBlocks = facts.companies
    .map((co) => {
      const tag = co.role === "brand" ? "Your brand" : "Rival";
      const plats = co.platforms
        .map(
          (p) =>
            `<li><strong>${esc(p.platform)}</strong>: ${p.posts} posts · avg ${fmtNum(p.avgLikes)} likes / ${fmtNum(p.avgComments)} comments / ${fmtNum(p.avgShares)} shares` +
            (p.avgViews > 0 ? ` / ${fmtNum(p.avgViews)} views` : "") +
            ` · cadence ${fmtNum(p.cadencePerDay)}/day · comment rate ${fmtNum(p.commentRate)}%</li>`,
        )
        .join("");
      return (
        `<h3 style="margin:16px 0 6px;font-size:15px;">${esc(co.name)} <span style="color:#666;font-weight:400;">(${tag})</span></h3>` +
        `<p style="margin:0 0 6px;font-size:13px;">Posts <strong>${co.posts}</strong> · avg engagement <strong>${fmtNum(co.avgEngagement)}</strong> · visual <strong>${co.visualPct}%</strong></p>` +
        (plats ? `<ul style="margin:0;padding-left:18px;font-size:13px;line-height:1.45;">${plats}</ul>` : "")
      );
    })
    .join("");

  const topPostsHtml = facts.topPosts
    .slice(0, 5)
    .map((p, i) => {
      const hook = esc((p.caption || "").replace(/\s+/g, " ").trim().slice(0, 110));
      const link = p.href
        ? `<a href="${esc(p.href)}" style="color:#0b5fff;text-decoration:none;">open</a>`
        : "";
      return (
        `<li style="margin-bottom:8px;"><strong>${i + 1}.</strong> [${esc(p.company)} · ${esc(p.platform)}] ${hook}` +
        `<br/><span style="color:#555;font-size:12px;">${p.likes} likes · ${p.comments} comments · ${p.shares} shares` +
        (p.views > 0 ? ` · ${p.views} views` : "") +
        ` · score ${fmtNum(p.score)} · ${esc(p.format)}${link ? ` · ${link}` : ""}</span></li>`
      );
    })
    .join("");

  const formatMixHtml = facts.formatMix
    .slice(0, 6)
    .map((f) => `${esc(f.format)} ${f.pct}% (${f.count})`)
    .join(" · ");
  const themesHtml = facts.topThemes
    .slice(0, 6)
    .map((t) => `${esc(t.theme)} (${t.count})`)
    .join(" · ");

  const bullets = (items: string[], title: string) =>
    items.length
      ? `<h3 style="margin:16px 0 6px;font-size:15px;">${esc(title)}</h3><ul style="margin:0;padding-left:18px;font-size:13px;line-height:1.45;">${items
          .slice(0, 4)
          .map((s) => `<li>${esc(s)}</li>`)
          .join("")}</ul>`
      : "";

  const emailHtml = [
    `<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111;max-width:640px;">`,
    `<p style="margin:0 0 12px;font-size:14px;line-height:1.5;">Scout finished for <strong>${esc(facts.brandName)}</strong>.</p>`,
    `<table style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:12px;">`,
    `<tr><td style="padding:6px 8px;background:#f4f4f5;border:1px solid #e4e4e7;">Window</td><td style="padding:6px 8px;border:1px solid #e4e4e7;">${esc(facts.window.label)} (${facts.window.days} days)</td></tr>`,
    `<tr><td style="padding:6px 8px;background:#f4f4f5;border:1px solid #e4e4e7;">Posts in window</td><td style="padding:6px 8px;border:1px solid #e4e4e7;"><strong>${totalPosts}</strong> (brand ${brandPosts} · rivals ${rivalPosts})</td></tr>`,
    `</table>`,
    companyBlocks,
    formatMixHtml
      ? `<h3 style="margin:16px 0 6px;font-size:15px;">Format mix</h3><p style="margin:0;font-size:13px;">${formatMixHtml}</p>`
      : "",
    themesHtml
      ? `<h3 style="margin:16px 0 6px;font-size:15px;">Top themes</h3><p style="margin:0;font-size:13px;">${themesHtml}</p>`
      : "",
    topPostsHtml
      ? `<h3 style="margin:16px 0 6px;font-size:15px;">Top posts by engagement</h3><ol style="margin:0;padding-left:18px;font-size:13px;line-height:1.45;">${topPostsHtml}</ol>`
      : "",
    bullets(facts.winningBecause, "What's working"),
    bullets(facts.leakingBecause, "Watch / fix"),
    `<p style="margin:18px 0 0;font-size:13px;color:#444;">Next: open Findings, then War Room for the full brief and counter-moves.</p>`,
    `</div>`,
  ]
    .filter(Boolean)
    .join("");

  return { shortBody, emailBody, emailHtml };
}
