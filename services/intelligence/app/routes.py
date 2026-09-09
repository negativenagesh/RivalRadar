from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.digest import generate_digest
from app.ingestion_client import fetch_posts
from app.models import Digest
from app.schemas import DigestRead

router = APIRouter()


@router.post("/digests/generate", response_model=DigestRead)
async def trigger_digest_generation(session: AsyncSession = Depends(get_session)) -> Digest:
    posts = await fetch_posts()
    return await generate_digest(session, posts)


@router.get("/digests/latest", response_model=DigestRead)
async def get_latest_digest(session: AsyncSession = Depends(get_session)) -> Digest:
    result = await session.scalars(select(Digest).order_by(Digest.generated_at.desc()).limit(1))
    digest = result.first()
    if digest is None:
        raise HTTPException(status_code=404, detail="No digest has been generated yet")
    return digest


@router.get("/digests", response_model=list[DigestRead])
async def list_digests(session: AsyncSession = Depends(get_session)) -> list[Digest]:
    result = await session.scalars(select(Digest).order_by(Digest.generated_at.desc()))
    return list(result.all())
