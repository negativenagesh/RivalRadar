# RivalRadar examples

Operator screenshots and Format Studio meme outputs kept for docs / regression vibe — **not** golden fixtures for CI.

Captured from a live local session (`localhost:3000`) with Pixis brand context and Nova Wear scout posts already loaded.

---

## UI tour

Screenshots live in [`ui/`](ui/).

| # | Shot | Route / surface | What you're looking at |
|---|------|-----------------|------------------------|
| 01 | [ui/01-home.png](ui/01-home.png) | `/` | Marketing home — Watch → Cluster → Draft → Approve beats, live-scout preview |
| 02 | [ui/02-mission-context.png](ui/02-mission-context.png) | `/mission` · step 1 | Mission Control context — brand drop, model keys, social stack, rivals |
| 03 | [ui/03-notifications.png](ui/03-notifications.png) | Nav bell | Notification center — Scout done, calendar remind, Studio ready + optional email |
| 04 | [ui/04-models.png](ui/04-models.png) | Models sheet | Operator secrets — Gemini / DeepSeek / NVIDIA / Agnes keys + live text/image picks |
| 05 | [ui/05-mission-scout.png](ui/05-mission-scout.png) | `/mission` · step 2 | Live Scout — lookback, Connect Center, Start Scout, operator feed + event log |
| 06 | [ui/06-scout-in-window-posts.png](ui/06-scout-in-window-posts.png) | Scout · In-window | Extracted posts for the lookback (clear on new Start Scout; stream in as they land) |
| 07 | [ui/07-mission-findings.png](ui/07-mission-findings.png) | `/mission` · step 3 | Findings — company vs rivalry intel dump with engagement chips |
| 08 | [ui/08-mission-report-intel.png](ui/08-mission-report-intel.png) | `/mission` · step 4 | War Room intel brief — scoreboard, agents, Main brief tabs |
| 09 | [ui/09-format-studio.png](ui/09-format-studio.png) | Report · Format Studio | Dual-path Full generate / Fast paint, Post to platform + Schedule, Comment sniper |
| 10 | [ui/10-calendar.png](ui/10-calendar.png) | `/calendar` | Content calendar — remind-to-stage slots (never autopost); Stage in Connect |
| 11 | [ui/11-digest.png](ui/11-digest.png) | `/digest` | Weekly digest — trending themes, coverage gaps, engagement clusters |
| 12 | [ui/12-review.png](ui/12-review.png) | `/review` | Review queue — approve / edit / reject with compliance flags |

### Quick previews

#### Home

![Home](ui/01-home.png)

#### Mission · Context

![Mission Context](ui/02-mission-context.png)

#### Notifications

![Notifications](ui/03-notifications.png)

#### Models

![Models](ui/04-models.png)

#### Live Scout

![Live Scout](ui/05-mission-scout.png)

#### In-window posts

![In-window posts](ui/06-scout-in-window-posts.png)

#### Findings

![Findings](ui/07-mission-findings.png)

#### Intel brief

![Intel brief](ui/08-mission-report-intel.png)

#### Format Studio

![Format Studio](ui/09-format-studio.png)

#### Calendar

![Calendar](ui/10-calendar.png)

#### Digest

![Digest](ui/11-digest.png)

#### Review queue

![Review](ui/12-review.png)

---

## Format Studio meme examples

Real outputs from Mission → Format studio (`format=meme`) against a Pixis vs Smartly scout roast pack.
These are **operator screenshots of generated PNGs** — not golden fixtures for CI.

| # | File | Era | Overlay (from UI / logs) | Caption / notes (from UI logs) |
|---|------|-----|--------------------------|--------------------------------|
| 01 | [01-early-dashboards-are-memes.jpg](01-early-dashboards-are-memes.jpg) | Pre–Meme Lord harden | Intended: `Your dashboards are memes` (image misspelled *dashwoards*) | *Your dashboards are memes. We'll crunch the jokes.* · Why this slaps: pokes fun at overly crunched dashboards · Overlay: `Your dashboards are memes` |
| 02 | [02-early-maximized-performance.jpg](02-early-maximized-performance.jpg) | Early studio | Painted: `Welcome to maximized performance` | Log intended overlay was *Your dashboards are memes*; image model drifted to corporate slogan text |
| 03 | [03-soft-smartly-18-likes.jpg](03-soft-smartly-18-likes.jpg) | Roast-pack era, still soft | `Smartly: Likes` / `18 Likes, 0 Comments` | Scoreboard-on-laptop frame — metrics painted literally from FACTS |
| 04 | [04-soft-zero-comments-real-action.jpg](04-soft-zero-comments-real-action.jpg) | Spice ~4, still soft | `Smartly: 0 Comments. Pixis: Real Action.` | Corporate-drama still; comparison scoreboard overlay |
| 05 | [05-spice4-dead-comment-zoo.jpg](05-spice4-dead-comment-zoo.jpg) | After HARD Gen-Z pass (#32) | `Smartly: Dead Comment Zoo` | Absurdist metaphor (neon T‑rex / dead comments) — roast fuel from rival comment death, not a chart UI |

### What “good” looks like now

- Overlay = punchline (not `Rival: N Likes`)
- Frame = absurdist metaphor about a **real** rival flaw from the roast pack
- No laptop/dashboard/analytics UI in-frame
- Letter-perfect English spelling on overlay words

Prompts live in `services/generation/app/agents/prompts.py` (`MEME_LORD`, `IMAGE_NEGATIVES`).
