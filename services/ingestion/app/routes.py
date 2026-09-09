from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.fixture import FixtureConnector
from app.db import get_session
from app.ingest import run_ingestion
from app.models import CompetitorAccount, CompetitorPost
from app.schemas import CompetitorAccountRead, CompetitorPostRead, IngestionRunResult

router = APIRouter()


@router.post("/ingest/run", response_model=IngestionRunResult)
async def trigger_ingestion(session: AsyncSession = Depends(get_session)) -> IngestionRunResult:
    connector = FixtureConnector()
    return await run_ingestion(session, connector)


@router.get("/accounts", response_model=list[CompetitorAccountRead])
async def list_accounts(
    session: AsyncSession = Depends(get_session),
) -> list[CompetitorAccount]:
    result = await session.scalars(select(CompetitorAccount))
    return list(result.all())


@router.get("/posts", response_model=list[CompetitorPostRead])
async def list_posts(session: AsyncSession = Depends(get_session)) -> list[CompetitorPost]:
    result = await session.scalars(select(CompetitorPost))
    return list(result.all())
