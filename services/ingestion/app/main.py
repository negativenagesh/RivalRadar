from fastapi import FastAPI

app = FastAPI(title="RivalRadar Ingestion Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ingestion"}
