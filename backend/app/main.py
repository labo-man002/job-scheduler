



from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.logging_config import configure_logging
from app.routers import clients, clusters, institutes, jobs, nodes, quotas, reservations

configure_logging()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server (apps/frontend)
    allow_methods=["*"],
    allow_headers=["*"],
)

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