

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.logging_config import configure_logging
from app.metrics import collect_once
from app.routers import clients, clusters, institutes, jobs, nodes, quotas, reservations

configure_logging()

METRICS_INTERVAL_SECONDS = 15


async def _collect_metrics_periodically():
    while True:
        collect_once()
        await asyncio.sleep(METRICS_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_collect_metrics_periodically())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server (apps/frontend)
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)  # GET /metrics

app.include_router(jobs.router)
app.include_router(clients.router)
app.include_router(institutes.router)
app.include_router(clusters.router)
app.include_router(nodes.router)
app.include_router(quotas.router)
app.include_router(reservations.router)


@app.get("/")
async def main():
    return {"message": "Hello World"}