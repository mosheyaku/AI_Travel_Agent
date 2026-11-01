import asyncio
import json

from pydantic import BaseModel, ValidationError
from typing import Literal

from app.llm import generate_text
from app.search import search_attractions


DurationType = Literal["short", "half_day", "full_day", "unknown"]


def classify_duration(duration_minutes: int) -> DurationType:
    if duration_minutes <= 120:
        return "short"

    if duration_minutes < 420:
        return "half_day"

    return "full_day"


class DurationAssessment(BaseModel):
    duration_type: DurationType
    duration_minutes: int | None = None
    source_indices: list[int]


async def enrich_attraction_duration(attraction: dict, destination: str) -> dict:
    """Find source-supported duration information for one attraction."""

    existing_duration = attraction.get("duration_minutes")

    if existing_duration is not None:
        return {
            **attraction,
            "duration_type": classify_duration(existing_duration),
        }

    unknown_duration = {
        **attraction,
        "duration_type": "unknown",
        "duration_minutes": None,
    }

    query = (
        f'"{attraction["name"]}" {destination} '
        "visit duration tour length how long hours"
    )

    response = await asyncio.to_thread(search_attractions, query)

    results = [
        result
        for result in response.get("results", [])
        if result.get("url") and result.get("content")
    ]

    if not results:
        return unknown_duration

    source_text = "\n\n".join(
        f"[{index}] {result['title']}\n"
        f"URL: {result['url']}\n"
        f"Content: {result['content']}"
        for index, result in enumerate(results, start=1)
    )

    prompt = f"""
You are verifying the expected visit duration of a travel attraction.

Attraction: {attraction["name"]}
Destination: {destination}
Activity type: {attraction.get("activity_type", "unknown")}

Web sources:
{source_text}

Determine the duration of the specific recommended visitor experience.

Rules:
- Use only information explicitly supported by the sources.
- Do not estimate duration from the attraction category alone.
- Do not confuse travel time from a city with activity duration.
- Do not confuse opening hours with visit duration.
- Do not use a multi-attraction tour duration for a single attraction.
- Use "short" for a visit lasting up to about 2 hours.
- Use "half_day" for a visit lasting more than 2 hours but less than a full day.
- Use "full_day" only when a full-day experience is explicitly supported.
- If evidence is missing or ambiguous, use "unknown".
- Cite the numbered sources supporting the classification.
- If duration_type is "unknown", return an empty source_indices list.
- Extract duration_minutes only when the sources explicitly state
  the duration of the specific visitor experience.
- Convert explicitly stated hours to minutes.
- Do not invent a precise duration from duration_type.
- If sources provide a duration range, use null for duration_minutes.
- If no exact duration is supported, use null.
- For a general park, garden, trail, or waterfall, do not use a tour
  package's duration as the independent visit duration.
- A source saying an attraction is open for 8 hours is NOT evidence
  that visitors spend 8 hours there.
- If duration_minutes is provided, classify duration_type consistently.
- Return valid JSON only.


JSON structure:
{{
  "duration_type": "unknown",
  "duration_minutes": null,
  "source_indices": []
}}
"""

    response_text = await generate_text(prompt)

    try:
        assessment = DurationAssessment.model_validate(
            json.loads(response_text)
        )
    except (json.JSONDecodeError, ValidationError):
            return unknown_duration

    valid_indices = set(range(1, len(results) + 1))

    if (
        assessment.duration_type == "unknown"
        or not assessment.source_indices
        or not set(assessment.source_indices).issubset(valid_indices)
    ):
        return unknown_duration

    duration_minutes = assessment.duration_minutes

    if duration_minutes is not None:
        if duration_minutes <= 0 or duration_minutes > 1440:
            return unknown_duration
        duration_type = classify_duration(duration_minutes)
    else:
        # A source-supported duration category is useful even when a
        # precise minute count is unavailable. The scheduler will use
        # its existing category estimate and mark the schedule estimated.
        duration_type = assessment.duration_type

    return {
        **attraction,
        "duration_type": duration_type,
        "duration_minutes": duration_minutes,
    }


async def enrich_attraction_durations(
    recommendations: list[dict],
    destination: str,
) -> list[dict]:
    """Enrich missing durations while preserving attraction order."""
    return list(
        await asyncio.gather(
            *[
                enrich_attraction_duration(attraction, destination)
                for attraction in recommendations
            ]
        )
    )
