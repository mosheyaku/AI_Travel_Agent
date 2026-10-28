import asyncio
import json
from pydantic import ValidationError

from app.llm import generate_text
from app.schemas import AttractionRecommendation, AttractionRecommendations
from app.search import search_attractions
from app.deduplication import deduplicate_attractions
from app.verification import verify_recommendations
from app.attraction_locations import validate_attraction_locations


async def recommend_attractions(query: str | list[str], destination: str | None = None,) -> dict:
    """Find and validate attraction recommendations for each search query."""
    queries = [query] if isinstance(query, str) else query

    search_responses = await asyncio.gather(
        *[
            asyncio.to_thread(search_attractions, item)
            for item in queries
        ]
    )

    sources = []
    seen_urls = set()
    recommendations = []
    seen_names = set()

    for search_query, response in zip(queries, search_responses):
        query_sources = []

        for result in response.get("results", []):
            url = result.get("url")

            if not url:
                continue

            if url not in seen_urls:
                seen_urls.add(url)
                sources.append({
                    "title": result["title"],
                    "url": url,
                    "content": result["content"],
                })

            source_index = next(
                i
                for i, source in enumerate(sources, start=1)
                if source["url"] == url
            )

            query_sources.append((source_index, result))

        if not query_sources:
            continue

        source_text = "\n\n".join(
            f"[{index}] {result['title']}\n"
            f"URL: {result['url']}\n"
            f"Content: {result['content']}"
            for index, result in query_sources
        )

        prompt = f"""
You are a travel planning assistant.

User request: {search_query}

Use only the following web sources:
{source_text}

Return a JSON object with this exact structure:
{{
  "recommendations": [
    {{
      "name": "Attraction name",
      "category": "adventure",
      "duration_type": "unknown",
      "description": "Description supported by the sources",
      "relevance_reason": "Why it matches the user's request",
      "source_indices": [1]
    }}
  ]
}}

Requirements:
- Answer in English.
- Return up to 5 distinct attraction recommendations.
- Do not invent attractions.
- Each recommendation must represent one specific, identifiable attraction,
  location, trail, park, or activity provider mentioned in the sources.
- Use the actual name of the attraction as it appears in the sources.
- Do not use generic activity names such as "Ziplining in the Jungle",
  "ATV Jungle Adventure", or "Elephant Sanctuary Experience".
- If the source mentions a specific provider, use its name instead of
  describing the general activity.
- Do not combine multiple attractions or providers into one recommendation.
- If a source only describes a general activity without identifying
  a specific location or provider, do not recommend it.
- Do not rename attractions to make them sound more exciting.
- Prioritize attractions matching the specific user request.
- Only recommend attractions in the requested destination or nearby area.
- Do not include attractions elsewhere in the country.
- Use only facts supported by the provided sources.
- source_indices must reference the source numbers shown above.
- Do not invent details, prices, opening hours, distances, or travel times.
- Use only these categories: adventure, nature, culture, food, wildlife, relaxation, other.
- Classify attractions by their actual activity, not the user's requested category.
- Temples and historical sites belong to culture.
- Hiking, waterfalls, and scenic areas belong to nature.
- Animal encounters belong to wildlife.
- Return valid JSON only, without Markdown fences.
- Reject category pages, collections of attractions, and generic
  attraction labels that do not identify one specific visitable place.
- Classify duration_type as short, half_day, full_day, or unknown.
- Use short only when the sources indicate an activity lasting up to about 2 hours.
- Use half_day only when the sources indicate an activity lasting several hours.
- Use full_day only when the sources explicitly describe a full-day activity.
- If the duration is not supported by the sources, use unknown.
- Never infer duration_type from the attraction category alone.
"""

        valid_indices = {index for index, _ in query_sources}

        for attempt in range(2):
            response_text = await generate_text(prompt)

            print(f"LLM response for '{search_query}', attempt {attempt + 1}: "
            f"{response_text!r}",
            flush=True,
)

            try:
                response_data = json.loads(response_text)
                raw_recommendations = response_data["recommendations"]

                if not isinstance(raw_recommendations, list):
                    raise ValueError("Recommendations must be a list.")

                valid_recommendations = []

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

                    name = recommendation.name.strip().casefold()

                    if name in seen_names:
                        continue

                    valid_recommendations.append(recommendation)

                    if len(valid_recommendations) == 5:
                        break

                if valid_recommendations:
                    for recommendation in valid_recommendations:
                        name = recommendation.name.strip().casefold()
                        seen_names.add(name)
                        recommendations.append(recommendation)

                    break

                raise ValueError("No valid recommendations were returned.")

            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                print(f"Recommendation failed for '{search_query}', "
                f"attempt {attempt + 1}: {exc!r}",flush=True,)

                prompt += f"""

Your previous response contained no valid recommendations.

Validation error: {exc}
Available source indices: {sorted(valid_indices)}

Return valid JSON using only these source indices.
"""

    print(f"Total valid recommendations: {len(recommendations)}",flush=True,)

    if sources and not recommendations:
        raise ValueError("The model returned no valid recommendations after retry.")
    
    print(f"Total valid recommendations: {len(recommendations)}", flush=True)

    recommendations = deduplicate_attractions(recommendations)
    recommendations = await verify_recommendations(
    recommendations,
    sources,
    destination,
    )

    if destination:
        recommendations = await validate_attraction_locations(recommendations,destination,)
    
    parsed = AttractionRecommendations(
        recommendations=recommendations[:15]
    )

    print("Recommendations schema validation passed", flush=True)


    return {
        "query": query,
        "recommendations": parsed.model_dump()["recommendations"],
        "sources": [
            {"title": source["title"], "url": source["url"]}
            for source in sources
        ],
    }
