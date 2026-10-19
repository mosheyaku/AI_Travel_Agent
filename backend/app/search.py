from langchain_tavily import TavilySearch

from app.config import settings


search_tool = TavilySearch(
    max_results=5,
    tavily_api_key=settings.tavily_api_key,
)


def search_attractions(query: str) -> dict:
    """Search the web for attractions and return results with sources."""
    return search_tool.invoke({"query": query})
