from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_models
from app.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    await init_models()
    yield


app = FastAPI(title="RivalRadar Gateway Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "gateway"}
