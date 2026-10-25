import json

from app.llm import generate_text
from app.schemas import AttractionRecommendation


async def verify_recommendations(
    recommendations: list[AttractionRecommendation],
    sources: list[dict],
) -> list[AttractionRecommendation]:
    if not recommendations:
        return []

    evidence = []

    for index, recommendation in enumerate(recommendations):
        supporting_sources = [
            {
                "title": sources[source_index - 1]["title"],
                "content": sources[source_index - 1]["content"],
            }
            for source_index in recommendation.source_indices
        ]

        evidence.append({
            "id": index,
            "name": recommendation.name,
            "description": recommendation.description,
            "sources": supporting_sources,
        })

    prompt = f"""
You are a travel recommendation fact-checker.

Review each attraction using only its provided sources.

Attractions and evidence:
{json.dumps(evidence, ensure_ascii=False)}

Return JSON in this format:
{{
  "results": [
    {{
      "id": 0,
      "verified": true,
      "description": "Corrected description supported by the sources"
    }}
  ]
}}

Requirements:
- Verify that each attraction is identifiable in its sources.
- If an attraction exists but its description contains unsupported details,
  remove those details and provide a corrected description.
- Preserve accurate information.
- Reject an attraction only if its identity cannot be established
  or the sources contain insufficient information to describe it.
- Do not invent activities, locations, prices, durations, or other facts.
- Keep descriptions short, specific, and useful for travelers.
- Evaluate every attraction independently.
- Return exactly one result for each attraction ID.
- Return valid JSON only.
"""

    response_text = await generate_text(prompt)

    try:
        response = json.loads(response_text)
        results = response["results"]

        if not isinstance(results, list):
            raise ValueError("Invalid verification results.")

        verified = []
        seen_ids = set()

        for item in results:
            index = item["id"]

            if (
                type(index) is not int
                or index < 0
                or index >= len(recommendations)
                or index in seen_ids
            ):
                raise ValueError("Invalid recommendation ID.")

            seen_ids.add(index)

            if type(item["verified"]) is not bool:
                raise ValueError("Invalid verification status.")

            if not item["verified"]:
                continue

            description = item["description"]

            if not isinstance(description, str) or not description.strip():
                raise ValueError("Invalid verified description.")

            recommendation = recommendations[index].model_copy(
                update={"description": description.strip()}
            )
            verified.append(recommendation)

        if len(seen_ids) != len(recommendations):
            raise ValueError("Missing verification results.")

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("The model returned invalid verification results.") from exc

    return verified