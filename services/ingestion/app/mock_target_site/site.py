"""A tiny static "fake social feed" the browser agent can safely scrape.

Real platforms (Instagram/LinkedIn/X) prohibit automated scraping in their
Terms of Service. This bundled site reproduces the same account/post shape
as the fixtures so SocialProfileConnector has a legal, stable, always-on
target to demonstrate real browser-driven ingestion end-to-end. Point
SocialProfileConnector at a different base_url only if you have your own
authorized access to a real target.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

_CARD_TEMPLATE = """
<article class="post-card" data-post-id="{external_post_id}" data-format="{format}">
  <h3 class="post-caption">{caption}</h3>
  <p class="post-themes" data-themes="{theme_tags}">{theme_tags}</p>
  <img class="post-image" src="{image_url}" alt="post image" />
  <ul class="post-stats">
    <li data-stat="likes">{likes}</li>
    <li data-stat="comments">{comments}</li>
    <li data-stat="shares">{shares}</li>
  </ul>
  <time class="post-posted-at" datetime="{posted_at}">{posted_at}</time>
</article>
"""

_PAGE_TEMPLATE = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>{handle} — mock feed</title></head>
<body>
  <header class="profile-header" data-handle="{handle}" data-platform="{platform}">
    <h1 class="profile-name">{display_name}</h1>
  </header>
  <main class="post-feed">
    {cards}
  </main>
</body>
</html>
"""


def _load_fixtures() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fixtures = files("app.fixtures")
    accounts = json.loads((fixtures / "accounts.json").read_text())
    posts = json.loads((fixtures / "posts.json").read_text())
    return accounts, posts


def render_index() -> str:
    accounts, _ = _load_fixtures()
    links = "\n".join(
        f'<li><a href="/profile/{a["handle"].lstrip("@")}" '
        f'data-handle="{a["handle"]}">{a["display_name"]}</a></li>'
        for a in accounts
    )
    return f"<!doctype html><html><body><ul class='profile-list'>{links}</ul></body></html>"


def render_profile_page(handle_slug: str) -> str | None:
    accounts, posts = _load_fixtures()
    handle = f"@{handle_slug}"
    account = next((a for a in accounts if a["handle"] == handle), None)
    if account is None:
        return None

    account_posts = [p for p in posts if p["account_handle"] == handle]
    cards = "\n".join(
        _CARD_TEMPLATE.format(
            external_post_id=p["external_post_id"],
            format=p["format"],
            caption=p["caption"],
            theme_tags=",".join(p["theme_tags"]),
            image_url=p["image_url"],
            likes=p["likes"],
            comments=p["comments"],
            shares=p["shares"],
            posted_at=p["posted_at"],
        )
        for p in account_posts
    )
    return _PAGE_TEMPLATE.format(
        handle=account["handle"],
        platform=account["platform"],
        display_name=account["display_name"],
        cards=cards,
    )
