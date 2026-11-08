from langchain_tavily import TavilySearch

from app.config import settings


class AttractionSearchError(RuntimeError):
    """Raised when the attraction search provider fails."""


search_tool = TavilySearch(
    max_results=5,
    tavily_api_key=settings.tavily_api_key,
)


def search_attractions(query: str) -> dict:
    """Search for attractions and validate the provider response."""
    try:
        response = search_tool.invoke({"query": query})
    except Exception as exc:
        raise AttractionSearchError(
            "The attraction search provider is unavailable."
        ) from exc

    if not isinstance(response, dict):
        raise AttractionSearchError(
            "The attraction search provider returned an invalid response."
        )

    if response.get("error"):
        raise AttractionSearchError(
            f"The attraction search provider returned an error: " f"{response['error']}"
        )

    if not isinstance(response.get("results"), list):
        raise AttractionSearchError(
            "The attraction search provider returned no valid results field."
        )

    return response
