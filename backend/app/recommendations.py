
import asyncio

from app.llm import generate_text
from app.search import search_attractions


async def recommend_attractions(query: str) -> dict:
    """Find attractions online and generate source-grounded recommendations."""
    search_data = await asyncio.to_thread(search_attractions, query)
    results = search_data.get("results", [])

    if not results:
        return {
            "query": query,
            "recommendations": "No relevant search results were found.",
            "sources": [],
        }

    sources = [
        {
            "title": result["title"],
            "url": result["url"],
            "content": result["content"],
        }
        for result in results
    ]

    source_text = "\n\n".join(
        f"[{i}] {source['title']}\n"
        f"URL: {source['url']}\n"
        f"Content: {source['content']}"
        for i, source in enumerate(sources, start=1)
    )

    prompt = f"""
You are a travel planning assistant that uses information from web sources.

User request: {query}

Use the following sources to recommend relevant attractions:
{source_text}

Requirements:
- Answer in English.
- Recommend up to 5 relevant attractions and briefly explain why each is worth considering.
- Base your recommendations only on the provided sources. Do not invent missing details.
- Cite the relevant source number next to each recommendation, for example [1].
- Explicitly mention when the available information is insufficient to determine a detail.
- Do not provide prices, opening hours, or travel times unless they appear in the sources.
"""

    recommendations = await generate_text(prompt)

    return {
        "query": query,
        "recommendations": recommendations,
        "sources": [
            {"title": source["title"], "url": source["url"]}
            for source in sources
        ],
    }
