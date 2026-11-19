from fastapi import FastAPI

from app.routers import orders

app = FastAPI(title="Shop API")
app.include_router(orders.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
