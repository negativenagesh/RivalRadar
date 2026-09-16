#!/usr/bin/env python3
"""Local probe: LinkedIn on Obscura the way RivalRadar scouts.

Usage (Obscura already on :9222):
  BROWSER_ENGINE=obscura OBSCURA_CDP_URL=ws://127.0.0.1:9222 \\
    uv run --directory services/ingestion python ../../scripts/probe_linkedin_obscura.py

Optional cookies JSON file (Playwright cookie list):
  LINKEDIN_COOKIES_JSON=/path/to/cookies.json
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from datetime import date
from pathlib import Path

# Allow running from repo root via ingestion venv
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion"))

from app.connectors.oss.linkedin import LinkedInScraperError, fetch_linkedin_company_posts  # noqa: E402
from app.connectors.social_feed_parse import collect_post_urls, settle_page  # noqa: E402
from app.connectors.social_profile.browser import (  # noqa: E402
    BrowserSession,
    await_or_abandon,
    browser_engine,
    obscura_cdp_url,
)
from app.date_window import DateWindow  # noqa: E402

COMPANY = os.environ.get("LINKEDIN_COMPANY", "pixisai")
URL = f"https://www.linkedin.com/company/{COMPANY}/posts"
MOVE_DELAY_S = float(os.environ.get("MOVE_DELAY_S", "20"))
SCROLLS = int(os.environ.get("SCROLLS", "4"))
OSS_BUDGET_S = float(os.environ.get("OSS_BUDGET_S", "45"))


def _load_cookies() -> list[dict]:
    path = os.environ.get("LINKEDIN_COOKIES_JSON", "").strip()
    if not path:
        return []
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and "cookies" in data:
        data = data["cookies"]
    assert isinstance(data, list)
    return data


async def _pace(label: str) -> None:
    jitter = random.uniform(0.0, 3.0)
    wait = MOVE_DELAY_S + jitter
    print(f"  pace {label}: sleep {wait:.1f}s", flush=True)
    await asyncio.sleep(wait)


async def _human_scroll(page, n: int) -> None:
    for i in range(n):
        dy = random.randint(900, 2100)
        print(f"  scroll {i + 1}/{n} dy={dy}", flush=True)
        await page.mouse.wheel(0, dy)
        await settle_page(page, quiet_ms=random.randint(200, 600))
        await _pace(f"after_scroll_{i + 1}")


async def probe_browser_path(cookies: list[dict]) -> dict:
    print("\n=== A) RivalRadar browser path (collect_post_urls + paced scrolls) ===", flush=True)
    t0 = time.monotonic()
    out: dict = {"ok": False, "urls": [], "title": "", "url": "", "error": None, "seconds": 0.0}
    try:
        async with BrowserSession(headless=True, cookies=cookies) as session:
            assert session.page is not None
            page = session.page
            print(f"  goto {URL}", flush=True)
            await page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
            await settle_page(page, quiet_ms=400)
            await _pace("after_goto")
            out["title"] = await page.title()
            out["url"] = page.url
            print(f"  landed title={out['title']!r} url={out['url']}", flush=True)

            # Random scrolls like a human before RivalRadar collect
            await _human_scroll(page, SCROLLS)

            urls = await collect_post_urls(
                page,
                platform="linkedin",
                profile_url=URL,
                limit=20,
                max_scrolls=6,
            )
            out["urls"] = urls
            out["ok"] = True
            print(f"  collect_post_urls count={len(urls)}", flush=True)
            for u in urls[:8]:
                print(f"    - {u}", flush=True)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        print(f"  FAIL {out['error']}", flush=True)
    out["seconds"] = round(time.monotonic() - t0, 1)
    return out


async def probe_linkedin_scraper(cookies: list[dict]) -> dict:
    print("\n=== B) RivalRadar OSS path (linkedin_scraper / CompanyPostsScraper) ===", flush=True)
    t0 = time.monotonic()
    out: dict = {"ok": False, "posts": 0, "error": None, "seconds": 0.0, "timed_out": False}
    if not cookies:
        out["error"] = "no cookies — scraper requires Connect li_at (skipping live scrape)"
        print(f"  SKIP {out['error']}", flush=True)
        out["seconds"] = round(time.monotonic() - t0, 1)
        return out

    sessions = {"linkedin": {"cookies": cookies}}
    window = DateWindow(date_from=date(2026, 9, 1), date_to=date(2026, 9, 16))
    try:
        async with BrowserSession(headless=True, cookies=cookies) as session:
            assert session.page is not None
            print(f"  goto {URL}", flush=True)
            await session.page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
            await settle_page(session.page, quiet_ms=200)
            await _pace("before_scraper")
            print(f"  scraper budget={OSS_BUDGET_S}s", flush=True)
            try:
                _account, posts = await await_or_abandon(
                    fetch_linkedin_company_posts(
                        page=session.page,
                        run_id="probe-local",
                        handle=COMPANY,
                        url=URL,
                        window=window,
                        platform_sessions=sessions,
                        object_store=None,
                        max_posts=15,
                    ),
                    OSS_BUDGET_S,
                )
                out["posts"] = len(posts)
                out["ok"] = True
                print(f"  scraper posts_in_window={len(posts)}", flush=True)
            except TimeoutError as exc:
                out["timed_out"] = True
                out["error"] = str(exc)
                print(f"  TIMED OUT after {OSS_BUDGET_S}s (hang confirmed)", flush=True)
            except LinkedInScraperError as exc:
                out["error"] = str(exc)
                print(f"  scraper error: {exc}", flush=True)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        print(f"  FAIL {out['error']}", flush=True)
    out["seconds"] = round(time.monotonic() - t0, 1)
    return out


async def main() -> int:
    os.environ.setdefault("BROWSER_ENGINE", "obscura")
    os.environ.setdefault("OBSCURA_CDP_URL", "ws://127.0.0.1:9222")
    cookies = _load_cookies()
    print("engine=", browser_engine(), "cdp=", obscura_cdp_url(), flush=True)
    print("cookies=", len(cookies), "company=", COMPANY, "move_delay_s=", MOVE_DELAY_S, flush=True)

    browser = await probe_browser_path(cookies)
    oss = await probe_linkedin_scraper(cookies)

    print("\n=== REPORT ===", flush=True)
    print(json.dumps({"browser_path": browser, "oss_linkedin_scraper": oss}, indent=2))
    # Non-zero if browser path hard-failed
    if browser.get("error") and not browser.get("urls"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
