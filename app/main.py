



from fastapi import FastAPI

from app.logging_config import configure_logging
from app.routers import clients, clusters, institutes, jobs, quotas, reservations

configure_logging()

app = FastAPI()

app.include_router(jobs.router)
app.include_router(clients.router)
app.include_router(institutes.router)
app.include_router(clusters.router)
app.include_router(quotas.router)
app.include_router(reservations.router)


@app.get("/")
async def main():
    return {"message": "Hello World"}