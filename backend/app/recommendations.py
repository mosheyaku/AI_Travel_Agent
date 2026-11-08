import asyncio
import json
import time

from pydantic import ValidationError

from app.llm import generate_text
from app.schemas import AttractionRecommendation, AttractionRecommendations
from app.search import search_attractions
from app.deduplication import deduplicate_attractions, deduplicate_verified_attractions
from app.verification import verify_recommendations
from app.attraction_locations import validate_attraction_locations
from app.duration_enrichment import enrich_attraction_durations


def merge_recommendation_results(
    existing: dict,
    additional: dict,
) -> dict:
    """Merge recommendation batches without losing valid source references."""
    sources = [source.copy() for source in existing["sources"]]
    recommendations = [
        {
            **item,
            "source_indices": list(item["source_indices"]),
        }
        for item in existing["recommendations"]
    ]

    source_index_by_url = {
        source["url"]: index for index, source in enumerate(sources, start=1)
    }

    additional_source_map = {}

    for index, source in enumerate(additional["sources"], start=1):
        url = source["url"]

        if url not in source_index_by_url:
            sources.append(source.copy())
            source_index_by_url[url] = len(sources)

        additional_source_map[index] = source_index_by_url[url]

    recommendation_by_name = {
        item["name"].strip().casefold(): item for item in recommendations
    }

    recommendation_by_place_id = {
        item["google_place_id"]: item
        for item in recommendations
        if item.get("google_place_id")
    }

    for item in additional["recommendations"]:
        mapped_indices = []

        for index in item["source_indices"]:
            mapped_index = additional_source_map.get(index)

            if mapped_index is None:
                continue

            if mapped_index not in mapped_indices:
                mapped_indices.append(mapped_index)

        if not mapped_indices:
            continue

        name = item["name"].strip().casefold()
        place_id = item.get("google_place_id")

        duplicate = recommendation_by_name.get(name)

        if duplicate is None and place_id:
            duplicate = recommendation_by_place_id.get(place_id)

        if duplicate is not None:
            duplicate["source_indices"] = list(
                dict.fromkeys(duplicate["source_indices"] + mapped_indices)
            )
            continue

        merged_item = {
            **item,
            "source_indices": mapped_indices,
        }

        recommendations.append(merged_item)
        recommendation_by_name[name] = merged_item

        if place_id:
            recommendation_by_place_id[place_id] = merged_item

    return {
        "recommendations": recommendations,
        "sources": sources,
    }


def get_per_query_candidate_limit(
    max_attractions: int,
    query_count: int,
) -> int:
    """Calculate the candidate limit for each search query."""
    if max_attractions < 1:
        raise ValueError("max_attractions must be positive.")

    if query_count < 1:
        raise ValueError("query_count must be positive.")

    candidate_budget = max_attractions * 2

    return max(
        3,
        (candidate_budget + query_count - 1) // query_count,
    )


def select_diverse_attractions(
    recommendations: list[AttractionRecommendation],
    limit: int,
) -> list[AttractionRecommendation]:
    """Select attractions fairly across categories while preserving order."""
    if limit < 1:
        raise ValueError("limit must be positive.")

    if len(recommendations) <= limit:
        return recommendations.copy()

    grouped: dict[str, list[AttractionRecommendation]] = {}

    for recommendation in recommendations:
        grouped.setdefault(recommendation.category, []).append(recommendation)

    selected = []

    while len(selected) < limit:
        added = False

        for category_recommendations in grouped.values():
            if not category_recommendations:
                continue

            selected.append(category_recommendations.pop(0))
            added = True

            if len(selected) == limit:
                break

        if not added:
            break

    return selected


def build_recommendation_prompt(
    search_query: str,
    source_text: str,
    per_query_limit: int,
) -> str:
    """Build the source-grounded attraction extraction prompt."""
    return f"""
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
      "activity_type": "zipline",
      "duration_type": "unknown",
      "description": "Description supported by the sources",
      "relevance_reason": "Why it matches the user's request",
      "source_indices": [1],
      "booking_type": "unknown"
    }}
  ]
}}

Requirements:
- Answer in English.
- Return up to {per_query_limit} distinct attraction recommendations.
- Do not invent attractions.
- Each recommendation must represent one specific, identifiable attraction,
  location, trail, park, or activity provider mentioned in the sources.
- Use the actual name of the attraction as it appears in the sources.
- Do not use generic activity names such as "Ziplining in the Jungle",
  "ATV Jungle Adventure", or "Elephant Sanctuary Experience".
- If the source mentions a specific provider, use its name instead of
  describing the general activity.
- Do not combine multiple attractions or providers into one recommendation.
- Do not recommend a packaged tour under the name of one of its stops.
- Do not claim an activity at a park or dam solely because the broader
  region has that activity; verify that this exact provider offers it.
- Distinguish the attraction's own features from features of nearby places.
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
- Assign one specific activity_type to each attraction.
- Use lowercase snake_case for activity_type.
- Describe the primary visitor experience, not the attraction's name.
- Use the same activity_type for different providers offering essentially
  the same experience.
- Examples: zipline, elephant_sanctuary, rafting, hiking, waterfall,
  water_park, safari, temple, cooking_class.
- Do not create provider-specific activity types.
- Do not invent an activity type unsupported by the sources.

- Classify booking_type as self_guided, scheduled_activity,
  guided_tour, or unknown.
- Use self_guided for attractions visitors can explore independently.
- Use scheduled_activity for activities requiring a specific
  departure time or booked session.
- Use guided_tour for organized tours led by a guide.
- Base booking_type only on information supported by the sources.
- If the sources do not establish the booking type, use unknown.
- Do not assume booking type from activity_type alone.
"""


async def extract_query_recommendations(
    search_query: str,
    query_sources: list[tuple[int, dict]],
    per_query_limit: int,
    semaphore: asyncio.Semaphore,
) -> list[AttractionRecommendation]:
    """Extract recommendations from one query using bounded LLM concurrency."""
    if not query_sources:
        return []

    source_text = "\n\n".join(
        f"[{index}] {result['title']}\n"
        f"URL: {result['url']}\n"
        f"Content: {result['content']}"
        for index, result in query_sources
    )

    prompt = build_recommendation_prompt(
        search_query,
        source_text,
        per_query_limit,
    )

    valid_indices = {index for index, _ in query_sources}

    async with semaphore:
        for attempt in range(2):
            response_text = await generate_text(prompt)

            print(
                f"LLM response for '{search_query}', attempt {attempt + 1}: "
                f"{response_text!r}",
                flush=True,
            )

            try:
                response_data = json.loads(response_text)
                raw_recommendations = response_data["recommendations"]

                if not isinstance(raw_recommendations, list):
                    raise ValueError("Recommendations must be a list.")

                valid_recommendations = []
                local_seen_names = set()

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

                    if name in local_seen_names:
                        continue

                    local_seen_names.add(name)
                    valid_recommendations.append(recommendation)

                    if len(valid_recommendations) == per_query_limit:
                        break

                if valid_recommendations:
                    return valid_recommendations

                raise ValueError("No valid recommendations were returned.")

            except (
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                print(
                    f"Recommendation failed for '{search_query}', "
                    f"attempt {attempt + 1}: {exc!r}",
                    flush=True,
                )

                prompt += f"""

Your previous response contained no valid recommendations.

Validation error: {exc}
Available source indices: {sorted(valid_indices)}

Return valid JSON using only these source indices.
"""

    return []


async def recommend_attractions(
    query: str | list[str],
    destination: str | None = None,
    max_attractions: int = 15,
) -> dict:
    """Find and validate attraction recommendations for each search query."""
    queries = [query] if isinstance(query, str) else query

    if not queries:
        raise ValueError("At least one search query is required.")

    if max_attractions < 1:
        raise ValueError("max_attractions must be positive.")

    per_query_limit = get_per_query_candidate_limit(
        max_attractions,
        len(queries),
    )

    search_started_at = time.perf_counter()

    search_responses = await asyncio.gather(
        *[asyncio.to_thread(search_attractions, item) for item in queries]
    )

    for query, response in zip(queries, search_responses):
        results = response.get("results", [])

        print(
            "SEARCH DIAGNOSTIC | "
            f"query={query!r} | "
            f"result_count={len(results)} | "
            f"response_keys={list(response.keys())}",
            flush=True,
        )

    print(
        f"PERFORMANCE | search | "
        f"{time.perf_counter() - search_started_at:.2f} seconds",
        flush=True,
    )

    extraction_started_at = time.perf_counter()

    sources = []
    source_index_by_url = {}
    query_source_groups = []

    for response in search_responses:
        query_sources = []

        for result in response.get("results", []):
            url = result.get("url")

            if not url:
                continue

            if url not in source_index_by_url:
                sources.append(
                    {
                        "title": result["title"],
                        "url": url,
                        "content": result["content"],
                    }
                )
                source_index_by_url[url] = len(sources)

            source_index = source_index_by_url[url]
            query_sources.append((source_index, result))

        query_source_groups.append(query_sources)

    semaphore = asyncio.Semaphore(3)

    extraction_results = await asyncio.gather(
        *(
            extract_query_recommendations(
                search_query,
                query_sources,
                per_query_limit,
                semaphore,
            )
            for search_query, query_sources in zip(
                queries,
                query_source_groups,
            )
        )
    )

    recommendations = []
    seen_names = set()

    for query_recommendations in extraction_results:
        for recommendation in query_recommendations:
            name = recommendation.name.strip().casefold()

            if name in seen_names:
                continue

            seen_names.add(name)
            recommendations.append(recommendation)

    if sources and not recommendations:
        raise ValueError("The model returned no valid recommendations after retry.")

    print(
        f"PERFORMANCE | extraction | "
        f"{time.perf_counter() - extraction_started_at:.2f} seconds",
        flush=True,
    )

    print(
        f"Total valid recommendations: {len(recommendations)}",
        flush=True,
    )

    recommendations = deduplicate_attractions(recommendations)

    print(
        f"After deduplication: {len(recommendations)}",
        flush=True,
    )

    verification_started_at = time.perf_counter()

    recommendations = await verify_recommendations(
        recommendations,
        sources,
        destination,
    )

    print(
        f"PERFORMANCE | source_verification | "
        f"{time.perf_counter() - verification_started_at:.2f} seconds",
        flush=True,
    )

    print(
        f"After source verification: {len(recommendations)}",
        flush=True,
    )

    if destination:
        location_started_at = time.perf_counter()

        recommendations = await validate_attraction_locations(
            recommendations,
            destination,
        )

        recommendations = deduplicate_verified_attractions(recommendations)

        print(
            f"PERFORMANCE | location_validation | "
            f"{time.perf_counter() - location_started_at:.2f} seconds",
            flush=True,
        )

        print(
            "After location validation:",
            len(recommendations),
            "verified:",
            sum(
                recommendation.location_status == "verified"
                for recommendation in recommendations
            ),
            flush=True,
        )

        duration_started_at = time.perf_counter()

        enriched = await enrich_attraction_durations(
            [recommendation.model_dump() for recommendation in recommendations],
            destination,
        )

        print(
            f"PERFORMANCE | duration_enrichment | "
            f"{time.perf_counter() - duration_started_at:.2f} seconds",
            flush=True,
        )

        for attraction in enriched:
            print(
                "DURATION DEBUG:",
                attraction["name"],
                "type:",
                attraction.get("duration_type"),
                "minutes:",
                attraction.get("duration_minutes"),
                flush=True,
            )

        recommendations = [
            AttractionRecommendation.model_validate(item) for item in enriched
        ]

    parsed = AttractionRecommendations(
        recommendations=select_diverse_attractions(
            recommendations,
            max_attractions,
        )
    )

    print("Recommendations schema validation passed", flush=True)

    return {
        "query": query,
        "recommendations": parsed.model_dump()["recommendations"],
        "sources": [
            {"title": source["title"], "url": source["url"]} for source in sources
        ],
    }
