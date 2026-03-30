from fastapi import FastAPI

app = FastAPI(title="Slurm Observability API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health")
def api_health() -> dict[str, str]:
    return {"status": "ok", "api": "v1"}
