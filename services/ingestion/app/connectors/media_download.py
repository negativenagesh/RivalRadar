"""Shared media download into the object store (Findings visuals, not screenshots)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx

from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)


def _ext_from_content_type(content_type: str) -> str:
    ct = content_type.split(";")[0].strip().lower()
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    if "mp4" in ct:
        return ".mp4"
    return ".jpg"


async def download_media_to_store(
    store: ObjectStore,
    *,
    run_id: str,
    post_id: str,
    url: str,
    client: httpx.AsyncClient | None = None,
    headers: dict[str, str] | None = None,
) -> str | None:
    """Fetch remote media bytes and store under media/{run_id}/{post_id}.*"""
    owns = client is None
    http = client or httpx.AsyncClient(timeout=45.0, follow_redirects=True)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in post_id)[:80]
    try:
        response = await http.get(url, headers=headers or {})
        if response.status_code >= 400 or not response.content:
            return None
        content_type = response.headers.get("content-type", "image/jpeg")
        ext = _ext_from_content_type(content_type)
        key = f"media/{run_id}/{safe_id}{ext}"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)
        try:
            return await store.put(key, tmp_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)  # noqa: ASYNC240
            raise
    except Exception as exc:  # noqa: BLE001
        logger.info("media download failed for %s: %s", post_id, exc)
        return None
    finally:
        if owns:
            await http.aclose()


async def store_bytes(
    store: ObjectStore,
    *,
    run_id: str,
    post_id: str,
    data: bytes,
    content_type: str = "image/jpeg",
) -> str | None:
    if not data:
        return None
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in post_id)[:80]
    ext = _ext_from_content_type(content_type)
    key = f"media/{run_id}/{safe_id}{ext}"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return await store.put(key, tmp_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)  # noqa: ASYNC240
        raise
