from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.mock_target_site.site import render_index, render_profile_page

router = APIRouter(prefix="/mock-site", tags=["mock-site"])


@router.get("/", response_class=HTMLResponse)
async def mock_site_index() -> str:
    return render_index()


@router.get("/profile/{handle_slug}", response_class=HTMLResponse)
async def mock_site_profile(handle_slug: str) -> str:
    page = render_profile_page(handle_slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Unknown mock profile")
    return page
