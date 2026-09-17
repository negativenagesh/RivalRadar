#!/usr/bin/env python3
"""Local probe: LinkedIn on Obscura the way RivalRadar scouts.

Cookies come from the Connect **extension vault** (same as POST /ingestion/runs),
not from a user paste. Optional LINKEDIN_COOKIES_JSON remains a dev override.

Usage (Obscura already on :9222):
  BROWSER_ENGINE=obscura \\
    uv run --directory services/ingestion python ../../scripts/probe_linkedin_obscura.py
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion"))
sys.path.insert(0, str(ROOT / "services" / "gateway"))

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


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _load_cookies_from_json() -> list[dict]:
    path = os.environ.get("LINKEDIN_COOKIES_JSON", "").strip()
    if not path:
        return []
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and "cookies" in data:
        data = data["cookies"]
    assert isinstance(data, list)
    return data


async def _load_cookies_from_extension_vault() -> tuple[list[dict], str]:
    """Same path as gateway start_ingestion_run — Connect extension vault."""
    _load_dotenv()
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.config import settings
        from app.vault_sessions import cookies_for_platform, load_vaulted_platform_sessions
    except Exception as exc:  # noqa: BLE001
        return [], f"vault_import_failed:{type(exc).__name__}"

    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            vault = await load_vaulted_platform_sessions(
                session, workspace_id="default", platforms={"linkedin"}
            )
        cookies = cookies_for_platform(vault, "linkedin")
        if not cookies:
            return [], "vault_empty_no_linkedin_extension_session"
        return cookies, f"extension_vault cookies={len(cookies)}"
    except Exception as exc:  # noqa: BLE001
        return [], f"vault_error:{type(exc).__name__}:{str(exc)[:120]}"
    finally:
        await engine.dispose()


async def _load_cookies() -> tuple[list[dict], str]:
    file_cookies = _load_cookies_from_json()
    if file_cookies:
        return file_cookies, f"json_override cookies={len(file_cookies)}"
    return await _load_cookies_from_extension_vault()


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
        out["error"] = "no extension-vault cookies (Connect LinkedIn via extension first)"
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
                print(f"  TIMED OUT after {OSS_BUDGET_S}s", flush=True)
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
    cookies, source = await _load_cookies()
    print("engine=", browser_engine(), "cdp=", obscura_cdp_url(), flush=True)
    print("cookie_source=", source, "company=", COMPANY, "move_delay_s=", MOVE_DELAY_S, flush=True)

    browser = await probe_browser_path(cookies)
    oss = await probe_linkedin_scraper(cookies)

    print("\n=== REPORT ===", flush=True)
    print(
        json.dumps(
            {"cookie_source": source, "browser_path": browser, "oss_linkedin_scraper": oss},
            indent=2,
        )
    )
    if not cookies:
        return 3
    if browser.get("error") and not browser.get("urls"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
