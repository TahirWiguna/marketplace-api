from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.orders import router as orders_router
from app.routes.products import router as products_router

app = FastAPI(title="Marketplace Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products_router)
app.include_router(orders_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "marketplace-service"}
