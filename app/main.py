



from fastapi import FastAPI

from app.routers import workload


app = FastAPI()


app.include_router(workload.router)


@app.get("/")
async def main():
    return {"message": "Hello World"}