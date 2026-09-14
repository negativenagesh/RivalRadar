# Format Studio meme examples

Real outputs from Mission → Format studio (`format=meme`) against a Pixis vs Smartly scout roast pack.
These are **operator screenshots of generated PNGs** kept for docs / regression vibe — not golden fixtures for CI.

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
