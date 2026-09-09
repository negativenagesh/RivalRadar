from fastapi import FastAPI

app = FastAPI(title="RivalRadar Gateway Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "gateway"}
