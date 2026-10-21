
import asyncio
import json

from app.llm import generate_text
from app.search import search_attractions
from app.schemas import AttractionRecommendations
from pydantic import ValidationError


async def recommend_attractions(query: str) -> dict:
    """Find attractions online and generate validated recommendations."""
    search_data = await asyncio.to_thread(search_attractions, query)
    results = search_data.get("results", [])

    if not results:
        return {
            "query": query,
            "recommendations": [],
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
You are a travel planning assistant.

User request: {query}

Use only the following web sources:
{source_text}

Return a JSON object with this exact structure:
{{
  "recommendations": [
    {{
      "name": "Attraction name",
      "description": "Description supported by the sources",
      "relevance_reason": "Why it matches the user's request",
      "source_indices": [1]
    }}
  ]
}}

Requirements:
- Answer in English.
- Recommend up to 5 relevant attractions.
- Use only facts supported by the provided sources.
- source_indices must contain the one-based indices of sources that directly support the recommendation.
- Do not invent details, prices, opening hours, or travel times.
- Return valid JSON only, without Markdown fences.
"""

    response_text = await generate_text(prompt)

    try:
        parsed = AttractionRecommendations.model_validate(
            json.loads(response_text)
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            "The model returned an invalid recommendation response."
        ) from exc

    valid_indices = set(range(1, len(sources) + 1))

    for recommendation in parsed.recommendations:
        if any(index not in valid_indices for index in recommendation.source_indices):
            raise ValueError(
                "The model referenced a source index that does not exist."
            )

    return {
        "query": query,
        "recommendations": parsed.model_dump()["recommendations"],
        "sources": [
            {"title": source["title"], "url": source["url"]}
            for source in sources
        ],
    }
