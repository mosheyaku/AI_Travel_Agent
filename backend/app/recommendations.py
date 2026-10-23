import asyncio
import json

from app.llm import generate_text
from app.search import search_attractions
from app.schemas import AttractionRecommendation, AttractionRecommendations
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
      "category": "adventure",
      "description": "Description supported by the sources",
      "relevance_reason": "Why it matches the user's request",
      "source_indices": [1]
    }}
  ]
}}

Requirements:
- Answer in English.
- Recommend up to 5 relevant attractions.
- Prioritize attractions that directly match the user's requested activities and interests.
- Only recommend attractions in the requested destination or a reasonably nearby area.
- Do not include attractions elsewhere in the country just because they match the activity type.
- Classify each attraction according to the activity it actually offers, not merely the user's interest.
- Do not label wildlife encounters or ordinary sightseeing as adventure activities unless the source describes a relevant adventure activity.
- Exclude attractions when the sources do not provide enough evidence that they match the destination and request.
- Use only facts supported by the provided sources.
- source_indices must contain the one-based indices of sources that directly support the recommendation.
- Do not invent details, prices, opening hours, distances, or travel times.
- Do not recommend unrelated attractions just to fill the list.

Category rules:
- Use only these exact category values: adventure, nature, culture, food, wildlife, relaxation, other.
- Temples, shrines, historical sites, museums, and traditional architecture belong to culture.
- Hiking, waterfalls, caves, and scenic natural areas belong to nature, unless the main activity is an adventure sport.
- Animal encounters and wildlife observation belong to wildlife, unless another activity is clearly the main focus.
- Restaurants, food markets, and cooking classes belong to food.
- Beaches, spas, and leisure activities focused on rest belong to relaxation.
- If no category fits, use other.
- Never use attraction names or activity types as category values.
- Every recommendation must include a valid category.

Return valid JSON only, without Markdown fences.
"""


    valid_indices = set(range(1, len(sources) + 1))

    for attempt in range(2):
        response_text = await generate_text(prompt)

        try:
            response_data = json.loads(response_text)
            raw_recommendations = response_data["recommendations"]

            if not isinstance(raw_recommendations, list):
                raise ValueError("Recommendations must be a list.")

            valid_recommendations = []
            seen_names = set()

            for item in raw_recommendations:
                try:
                    recommendation = AttractionRecommendation.model_validate(item)
                except ValidationError:
                    continue

                if any(
                    index not in valid_indices
                    for index in recommendation.source_indices
                ):
                    continue

                normalized_name = recommendation.name.strip().casefold()

                if normalized_name in seen_names:
                    continue

                seen_names.add(normalized_name)
                valid_recommendations.append(recommendation)

                if len(valid_recommendations) == 5:
                    break

            if valid_recommendations:
                parsed = AttractionRecommendations(
                    recommendations=valid_recommendations
                )
                break

            raise ValueError("No valid recommendations were returned.")

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if attempt == 1:
                raise ValueError(
                    "The model returned no valid recommendations after retry."
                ) from exc

            prompt += f"""

Your previous response contained no usable recommendations.

Validation error: {exc}

Available source indices: {sorted(valid_indices)}

Return valid JSON with recommendations supported by these sources.
Do not invent source indices.
"""

    return {
        "query": query,
        "recommendations": parsed.model_dump()["recommendations"],
        "sources": [
            {"title": source["title"], "url": source["url"]}
            for source in sources
        ],
    }
