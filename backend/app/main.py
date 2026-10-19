
from fastapi import FastAPI

from app.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="An AI-powered travel planning agent.",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Check whether the backend is running."""
    return {"status": "ok"}
