from fastapi import FastAPI, Query, HTTPException

from app.config import settings
from app.search import search_attractions
from app.recommendations import recommend_attractions


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
def attraction_search(query: str = Query(min_length=3),) -> dict:
    """Search the web for travel attractions."""
    return search_attractions(query)


@app.get("/attractions/recommend")
async def attraction_recommendations(
    query: str = Query(min_length=3),
) -> dict:
    """Generate attraction recommendations based on web search."""
    try:
        return await recommend_attractions(query)
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="The recommendation service returned an invalid response.",
        ) from exc
