import asyncio
import json
import re
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.llm import generate_text
from app.search import search_attractions


DurationType = Literal["short", "half_day", "full_day", "unknown"]

DURATION_WORDS = re.compile(
    r"\b(?:duration|lasts?|lasting|hours?|hrs?|minutes?|mins?|"
    r"half.day|full.day|all.day|day.long)\b",
    re.IGNORECASE,
)

NUMBER = r"\d+(?:\.\d+)?"

EXACT_DURATION = re.compile(
    rf"\b({NUMBER})\s*(hours?|hrs?|minutes?|mins?)\b",
    re.IGNORECASE,
)

RANGE_DURATION = re.compile(
    rf"\b{NUMBER}\s*(?:-|–|—|to)\s*{NUMBER}\s*" r"(?:hours?|hrs?|minutes?|mins?)\b",
    re.IGNORECASE,
)

OPENING_HOURS = re.compile(
    r"\b(?:open|opening|operating|business)\s+hours?\b",
    re.IGNORECASE,
)


def extract_exact_durations(text: str) -> set[int]:
    """Extract exact duration values while excluding ranges."""
    if RANGE_DURATION.search(text):
        return set()

    durations = set()

    for match in EXACT_DURATION.finditer(text):
        value = float(match.group(1))
        unit = match.group(2).lower()

        minutes = value * 60 if unit.startswith(("hour", "hr")) else value

        if minutes.is_integer():
            durations.add(int(minutes))

    return durations


def classify_duration(duration_minutes: int) -> DurationType:
    """Classify an explicitly supported duration."""
    if duration_minutes <= 120:
        return "short"

    if duration_minutes < 420:
        return "half_day"

    return "full_day"


class DurationEvidence(BaseModel):
    source_index: int
    quote: str


class DurationAssessment(BaseModel):
    duration_type: DurationType
    duration_minutes: int | None = None
    evidence: list[DurationEvidence]


def normalize_quote(text: str) -> str:
    """Normalize whitespace without changing the quoted wording."""
    return re.sub(r"\s+", " ", text).strip()


def validate_duration_evidence(
    assessment: DurationAssessment,
    results: list[dict],
) -> bool:
    """Validate quoted evidence and its support for the claimed duration."""
    if not assessment.evidence:
        return False

    supported_exact_durations = set()
    supported_duration_types = set()

    for item in assessment.evidence:
        if type(item.source_index) is not int:
            return False

        if not 1 <= item.source_index <= len(results):
            return False

        quote = normalize_quote(item.quote)

        if not quote:
            return False

        source_content = normalize_quote(results[item.source_index - 1]["content"])

        if quote not in source_content:
            return False

        if not DURATION_WORDS.search(quote):
            return False

        if OPENING_HOURS.search(quote):
            return False

        exact_durations = extract_exact_durations(quote)
        supported_exact_durations.update(exact_durations)

        for duration in exact_durations:
            if duration > 0:
                supported_duration_types.add(classify_duration(duration))

        if re.search(r"\bhalf.day\b", quote, re.IGNORECASE):
            supported_duration_types.add("half_day")

        if re.search(
            r"\b(?:full.day|all.day|day.long)\b",
            quote,
            re.IGNORECASE,
        ):
            supported_duration_types.add("full_day")

    if assessment.duration_minutes is not None:
        return assessment.duration_minutes in supported_exact_durations

    return assessment.duration_type in supported_duration_types


async def enrich_attraction_duration(
    attraction: dict,
    destination: str,
) -> dict:
    """Find supported duration information without discarding prior evidence."""
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
You are verifying the duration of a specific travel attraction.

Attraction: {attraction["name"]}
Destination: {destination}
Activity type: {attraction.get("activity_type", "unknown")}
Booking type: {attraction.get("booking_type", "unknown")}

Web sources:
{source_text}

Determine the duration of the specific recommended visitor experience.

Rules:
- Use only information explicitly supported by the source CONTENT.
- Do not use the source title alone as evidence.
- Do not estimate duration from the attraction category.
- Do not confuse travel time with activity duration.
- Do not confuse opening hours with visit duration.
- Do not use a multi-attraction tour duration for a single attraction.
- Do not use a tour package's duration for an independent visit.
- A tour package and one of its stops are not the same experience.
- Use duration information only when it clearly refers to the
  exact named attraction and recommended visitor experience.
- Reject duration evidence referring to another provider,
  a nearby attraction, or an unrelated activity.
- Use "short" for a visit lasting up to 120 minutes.
- Use "half_day" for a visit lasting more than 120 but fewer than
  420 minutes.
- Use "full_day" for an explicitly supported full-day experience
  or an exact duration of at least 420 minutes.
- If evidence is missing or ambiguous, use "unknown".
- Extract duration_minutes only when the source explicitly states
  an exact duration for this specific visitor experience.
- Convert explicitly stated hours to minutes.
- Do not invent a precise duration from duration_type.
- If a source provides a duration range, return null for
  duration_minutes.
- Do not use opening hours as evidence of visit duration.
- Do not use a multi-day or overnight program as a single-day
  activity duration.
- If duration_minutes is provided, duration_type must agree
  with its classification.
- Include an exact quote from the source CONTENT supporting
  the duration.
- The quote must explicitly connect the duration to this
  attraction or visitor experience.
- Do not invent or paraphrase quotes.
- If no reliable evidence exists, return unknown with empty evidence.
- Return valid JSON only.

JSON structure:
{{
  "duration_type": "unknown",
  "duration_minutes": null,
  "evidence": [
    {{
      "source_index": 1,
      "quote": "Exact duration statement copied from the source"
    }}
  ]
}}
"""

    try:
        response_text = await generate_text(prompt)
        assessment = DurationAssessment.model_validate(json.loads(response_text))
    except (
        json.JSONDecodeError,
        ValidationError,
        TypeError,
        ValueError,
    ):
        return unknown_duration

    if assessment.duration_type == "unknown":
        return unknown_duration

    if not validate_duration_evidence(
        assessment,
        results,
    ):
        return unknown_duration

    duration_minutes = assessment.duration_minutes

    if duration_minutes is not None:
        if duration_minutes <= 0 or duration_minutes > 1440:
            return unknown_duration

        duration_type = classify_duration(duration_minutes)

        if duration_type != assessment.duration_type:
            return unknown_duration

        return {
            **attraction,
            "duration_type": duration_type,
            "duration_minutes": duration_minutes,
        }

    return {
        **attraction,
        "duration_type": assessment.duration_type,
        "duration_minutes": None,
    }


async def enrich_attraction_durations(
    recommendations: list[dict],
    destination: str,
) -> list[dict]:
    """Enrich attraction durations with bounded concurrency."""
    semaphore = asyncio.Semaphore(5)

    async def enrich_one(attraction: dict) -> dict:
        async with semaphore:
            return await enrich_attraction_duration(
                attraction,
                destination,
            )

    return list(
        await asyncio.gather(
            *(enrich_one(attraction) for attraction in recommendations)
        )
    )
