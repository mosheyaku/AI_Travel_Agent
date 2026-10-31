
import asyncio
import json
import logging

from app.llm import generate_text
from app.schemas import AttractionRecommendation


logger = logging.getLogger(__name__)


async def verify_recommendations(
    recommendations: list[AttractionRecommendation],
    sources: list[dict],
    destination: str | None = None,
) -> list[AttractionRecommendation]:
    """Verify attractions against their supporting web sources."""
    if not recommendations:
        return []

    semaphore = asyncio.Semaphore(3)

    async def verify_one(
        recommendation: AttractionRecommendation,
    ) -> AttractionRecommendation | None:
        valid_source_indices = [
            index
            for index in recommendation.source_indices
            if type(index) is int and 1 <= index <= len(sources)
        ]

        if len(valid_source_indices) != len(recommendation.source_indices):
            logger.warning(
                "Skipping '%s': invalid original source indices.",
                recommendation.name,
            )
            return None

        supporting_sources = [
            {
                "index": index,
                "title": sources[index - 1]["title"],
                "content": sources[index - 1]["content"],
            }
            for index in valid_source_indices
        ]

        if not supporting_sources:
            return None

        identification_prompt = f"""
Identify which sources explicitly refer to the named attraction.

Attraction: {recommendation.name}

Sources:
{json.dumps(supporting_sources, ensure_ascii=False)}

Return JSON:
{{
  "source_indices": []
}}

Requirements:
- Select only sources that explicitly identify the exact attraction.
- Do not select sources describing unnamed or similar attractions.
- Do not assume that two attractions are the same.
- Return an empty list if no source identifies the attraction.
- Use only the source indices provided.
- Allowed source indices: {valid_source_indices}
- Do not renumber source indices starting from 1.
- Return valid JSON only.
"""

        async with semaphore:
            identified_indices = None

            for attempt in range(2):
                try:
                    identification_text = await generate_text(
                        identification_prompt
                    )

                    identification = json.loads(identification_text)
                    indices = identification["source_indices"]

                    if (
                        not isinstance(indices, list)
                        or any(
                            type(index) is not int
                            or index not in valid_source_indices
                            for index in indices
                        )
                    ):
                        raise ValueError("Invalid source indices.")

                    identified_indices = list(dict.fromkeys(indices))
                    break

                except (
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    logger.warning(
                        "Source identification failed for '%s' "
                        "(attempt %s): %s",
                        recommendation.name,
                        attempt + 1,
                        exc,
                    )

                    if attempt == 0:
                        identification_prompt += (
                            "\nYour previous response was invalid."
                            f"\nAllowed indices: {valid_source_indices}."
                            "\nReturn only these indices, or an empty list."
                            "\nDo not renumber the sources."
                        )

            if identified_indices is None:
                logger.warning(
                    "Skipping '%s': source identification failed.",
                    recommendation.name,
                )
                return None

            if not identified_indices:
                return None

            identified_sources = [
                source
                for source in supporting_sources
                if source["index"] in identified_indices
            ]

            verification_prompt = f"""
You are a strict travel attraction fact-checker.

Requested destination: {destination or "Not specified"}

Attraction:
{json.dumps(recommendation.model_dump(), ensure_ascii=False)}

Verified identity sources:
{json.dumps(identified_sources, ensure_ascii=False)}

Return JSON:
{{
  "verified": true,
  "description": "Short, factual description",
  "activity_type": "hiking",
  "duration_type": "unknown"
}}

Requirements:
- Use only the verified identity sources.
- Include only facts explicitly connected to this exact attraction.
- Do not transfer details from other or unnamed attractions.
- Remove unsupported activities, facilities, distances, and claims.
- Do not invent information.
- If a destination is provided, confirm that the attraction is
  located there or reasonably accessible as a day trip.
- Reject attractions clearly outside the requested travel area.
- If geographic evidence is insufficient, reject the attraction.
- If verified, write a concise, accurate description.
- The recommendation must represent one specific, identifiable,
  visitable attraction, trail, park, or activity provider.
- Reject generic categories, collections of attractions, and
  umbrella names that represent multiple different places.
- A source page title is not sufficient proof that an attraction exists.
- Return valid JSON only.
- Verify the attraction's activity_type against the identified sources.
- activity_type must describe an actual visitor experience supported
  by the sources for this exact attraction.
- Do not retain the original activity_type if it is unsupported.
- If the original activity_type is unsupported but another specific
  visitor activity is explicitly supported, use that activity instead.
- If no specific visitor activity can be verified, return verified=false.
- Use lowercase snake_case for activity_type.
- Use the same activity_type for essentially identical experiences.
- Verify duration_type using only explicit source evidence.
- Allowed duration_type values: short, half_day, full_day, unknown.
- Use unknown when the duration is not established by the sources.
- Do not infer a full-day duration merely because the attraction
  is a national park or a large geographic area.
"""

            try:
                verification_text = await generate_text(
                    verification_prompt
                )
                response = json.loads(verification_text)

                if type(response["verified"]) is not bool:
                    raise ValueError("Invalid verification status.")

                if not response["verified"]:
                    return None

                description = response["description"]
                activity_type = response["activity_type"]
                duration_type = response["duration_type"]

                if (
                    not isinstance(description, str)
                    or not description.strip()
                ):
                    raise ValueError("Invalid verified description.")

                if (
                    not isinstance(activity_type, str)
                    or not activity_type.strip()
                    or not activity_type.isascii()
                    or not all(
                        character.islower()
                        or character.isdigit()
                        or character == "_"
                        for character in activity_type
                    )
                ):
                    raise ValueError("Invalid verified activity type.")

                if duration_type not in {
                    "short",
                    "half_day",
                    "full_day",
                    "unknown",
                }:
                    raise ValueError("Invalid verified duration type.")

                return recommendation.model_copy(
                    update={
                        "description": description.strip(),
                        "activity_type": activity_type,
                        "duration_type": duration_type,
                        "source_indices": identified_indices,
                    }
                )

            except (
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                logger.warning(
                    "Skipping '%s': fact verification failed: %s",
                    recommendation.name,
                    exc,
                )
                return None

    results = await asyncio.gather(
        *(verify_one(recommendation) for recommendation in recommendations)
    )

    return [result for result in results if result is not None]
