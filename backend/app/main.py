from fastapi import FastAPI, Query, HTTPException

from app.config import settings
from app.search import search_attractions
from app.recommendations import recommend_attractions
from app.schemas import TravelPreferences
from app.trip_planning import build_attraction_queries, get_attraction_search_limit
from app.travel_graph import travel_graph

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


@app.post("/trips/preferences")
def create_travel_preferences(
    preferences: TravelPreferences,
) -> TravelPreferences:
    """Validate and return travel preferences."""
    return preferences


@app.post("/trips/attractions")
async def trip_attractions(
    preferences: TravelPreferences,
) -> dict:
    """Recommend attractions based on travel preferences."""
    queries = build_attraction_queries(preferences)

    try:
        return await recommend_attractions(queries,destination=preferences.destination,
        max_attractions=get_attraction_search_limit(preferences),)
    except ValueError as exc:
        print(f"Trip attractions error: {exc!r}", flush=True)
        
        raise HTTPException(
            status_code=502,
            detail="The recommendation service returned an invalid response.",
        ) from exc



@app.post("/trips/generate")
async def generate_trip(
    preferences: TravelPreferences,
) -> dict:
    """Generate a trip using the LangGraph workflow."""
    try:
        result = await travel_graph.ainvoke({
            "preferences": preferences,
        })

        return {
            "trip": result["trip"],
            "sources": result["sources"],
        }

    except ValueError as exc:
        print(f"Trip generation error: {exc!r}", flush=True)

        raise HTTPException(
            status_code=502,
            detail="The trip planning service returned an invalid response.",
        ) from exc