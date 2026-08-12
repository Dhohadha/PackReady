from fastapi import FastAPI
from app.core.config import settings
from app.products.router import router as products_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Minimal PackReady backend core application",
    version="0.1.0"
)

app.include_router(products_router)

@app.get("/health")
def get_health() -> dict[str, str]:
    """
    Health check endpoint returning status and service name.
    """
    return {
        "status": "ok",
        "service": "packready-api"
    }

