from fastapi import FastAPI

app = FastAPI(title="RivalRadar Generation Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "generation"}
