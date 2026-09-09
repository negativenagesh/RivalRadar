from fastapi import FastAPI

app = FastAPI(title="RivalRadar Compliance Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "compliance"}
