from fastapi import FastAPI

app = FastAPI(title="RivalRadar Intelligence Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "intelligence"}
