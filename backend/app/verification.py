
import asyncio
import json

from app.llm import generate_text
from app.schemas import AttractionRecommendation


async def verify_recommendations(
    recommendations: list[AttractionRecommendation],
    sources: list[dict],
    destination: str | None = None,
) -> list[AttractionRecommendation]:
    if not recommendations:
        return []

    semaphore = asyncio.Semaphore(3)

    async def verify_one(
        recommendation: AttractionRecommendation,
    ) -> AttractionRecommendation | None:
        supporting_sources = [
            {
                "index": index,
                "title": sources[index - 1]["title"],
                "content": sources[index - 1]["content"],
            }
            for index in recommendation.source_indices
        ]

        identification_prompt = f"""
Identify which sources explicitly refer to the named attraction.

Attraction: {recommendation.name}

Sources:
{json.dumps(supporting_sources, ensure_ascii=False)}

Return JSON:
{{
  "source_indices": [1]
}}

Requirements:
- Select only sources that explicitly identify the exact attraction.
- Do not select sources describing unnamed or similar attractions.
- Do not assume that two attractions are the same.
- Return an empty list if no source identifies the attraction.
- Use only the source indices provided.
- Return valid JSON only.
"""

        async with semaphore:
            identification_text = await generate_text(identification_prompt)

            try:
                identification = json.loads(identification_text)
                identified_indices = identification["source_indices"]

                valid_indices = {
                    source["index"] for source in supporting_sources
                }

                if (
                    not isinstance(identified_indices, list)
                    or any(
                        type(index) is not int or index not in valid_indices
                        for index in identified_indices
                    )
                ):
                    raise ValueError("Invalid source indices.")

                identified_indices = list(dict.fromkeys(identified_indices))

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
  "description": "Short, factual description"
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
"""

                verification_text = await generate_text(verification_prompt)
                response = json.loads(verification_text)

                if type(response["verified"]) is not bool:
                    raise ValueError("Invalid verification status.")

                if not response["verified"]:
                    return None

                description = response["description"]

                if not isinstance(description, str) or not description.strip():
                    raise ValueError("Invalid verified description.")

                return recommendation.model_copy(
                    update={
                        "description": description.strip(),
                        "source_indices": identified_indices,
                    }
                )

            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    "The model returned invalid verification results."
                ) from exc

    results = await asyncio.gather(
        *(verify_one(recommendation) for recommendation in recommendations)
    )

    return [result for result in results if result is not None]
