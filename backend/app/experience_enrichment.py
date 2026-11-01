import asyncio
import json
import re
from datetime import datetime

from pydantic import BaseModel, ValidationError

from app.llm import generate_text
from app.search import search_attractions


class ExperienceWindowAssessment(BaseModel):
    start_time: str | None = None
    end_time: str | None = None
    source_index: int | None = None
    evidence: str | None = None


def valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def evidence_contains_time(evidence: str, value: str) -> bool:
    hour, minute = map(int, value.split(":"))

    # Accept explicit 24-hour times, with or without a leading zero.
    pattern = rf"(?<!\d)0?{hour}:{minute:02d}(?!\d)"
    return re.search(pattern, evidence) is not None


async def enrich_attraction_experience(
    attraction: dict,
    destination: str,
) -> dict:
    """Extract a source-supported fixed experience time window."""

    unknown = {
        **attraction,
        "experience_start_time": None,
        "experience_end_time": None,
    }

    query = (
        f'"{attraction["name"]}" {destination} '
        "activity session operating hours schedule start end official"
    )

    response = await asyncio.to_thread(search_attractions, query)

    results = [
        result
        for result in response.get("results", [])
        if result.get("url") and result.get("content")
    ]

    if not results:
        return unknown

    source_text = "\n\n".join(
        f"[{index}] {result.get('title', '')}\n"
        f"URL: {result['url']}\n"
        f"Content: {result['content']}"
        for index, result in enumerate(results, start=1)
    )

    prompt = f"""
You verify fixed operating windows for specific travel experiences.

Attraction: {attraction["name"]}
Destination: {destination}
Activity type: {attraction.get("activity_type", "unknown")}

Sources:
{source_text}

Find a fixed daily time window during which the specific recommended
visitor experience can take place.

Rules:
- Use only explicit evidence from the sources.
- Do not infer times from the attraction's name or activity type.
- Do not confuse the venue's general opening hours with a specific
  tour or activity schedule.
- General opening hours may be used only when the recommended
  experience is independently accessible throughout those hours.
- Do not use a booking site's customer-service hours.
- Do not use times belonging to another provider or attraction.
- Do not use a one-off event, dated promotion, or seasonal schedule
  as a permanent daily window.
- Do not infer a continuous window from several individual departures.
- Do not use schedules that depend on the day of the week or date.
- Return times only when both boundaries are explicitly stated.
- Return times in 24-hour HH:MM format.
- For this extraction, accept only source evidence that explicitly
  writes both times in 24-hour format.
- Copy an exact supporting text excerpt into evidence.
- If anything is unclear, return null values.
- Return valid JSON only.

JSON structure:
{{
  "start_time": null,
  "end_time": null,
  "source_index": null,
  "evidence": null
}}
"""

    response_text = await generate_text(prompt)

    try:
        assessment = ExperienceWindowAssessment.model_validate(
            json.loads(response_text)
        )
    except (json.JSONDecodeError, ValidationError, TypeError):
        return unknown

    start = assessment.start_time
    end = assessment.end_time
    index = assessment.source_index
    evidence = assessment.evidence

    if not all(
        [
            start,
            end,
            index is not None,
            evidence,
        ]
    ):
        return unknown

    if not valid_time(start) or not valid_time(end):
        return unknown

    if start >= end:
        return unknown

    if not 1 <= index <= len(results):
        return unknown

    source_content = results[index - 1]["content"]

    if evidence not in source_content:
        return unknown

    if not (
        evidence_contains_time(evidence, start)
        and evidence_contains_time(evidence, end)
    ):
        return unknown

    return {
        **attraction,
        "experience_start_time": start,
        "experience_end_time": end,
    }


async def enrich_attraction_experiences(
    recommendations: list[dict],
    destination: str,
) -> list[dict]:
    """Enrich experience windows while preserving recommendation order."""

    return list(
        await asyncio.gather(
            *[
                enrich_attraction_experience(attraction, destination)
                for attraction in recommendations
            ]
        )
    )