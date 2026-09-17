from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.db import init_models
from app.mock_target_site.routes import router as mock_site_router
from app.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    await init_models()
    from app.runs import sweep_orphaned_runs

    with suppress(Exception):
        await sweep_orphaned_runs()
    yield


app = FastAPI(title="RivalRadar Ingestion Service", lifespan=lifespan)
app.include_router(router)
app.include_router(mock_site_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ingestion"}
