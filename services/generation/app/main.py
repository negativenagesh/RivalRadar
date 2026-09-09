from fastapi import FastAPI

from app.routes import router

app = FastAPI(title="RivalRadar Generation Service")
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "generation"}
