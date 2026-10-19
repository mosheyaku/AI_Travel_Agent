from fastapi import FastAPI, Query

from app.config import settings
from app.search import search_attractions


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="An AI-powered travel planning agent.",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Check whether the backend is running."""
    return {"status": "ok"}


@app.get("/attractions/search")
def attraction_search(
    query: str = Query(min_length=3),
) -> dict:
    """Search the web for travel attractions."""
    return search_attractions(query)
