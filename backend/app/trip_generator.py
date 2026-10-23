
import json

from pydantic import ValidationError

from app.llm import generate_text
from app.schemas import TravelItinerary, TravelPreferences


async def generate_trip_plan(
    preferences: TravelPreferences,
    recommendations: list[dict],
) -> TravelItinerary:
    """Generate a daily trip plan from attraction recommendations."""
    attractions_text = json.dumps(recommendations, ensure_ascii=False)

    prompt = f"""
You are a travel planning assistant.

Create a {preferences.duration_days}-day trip plan for
{preferences.destination}.

Travel pace: {preferences.pace}
User interests: {", ".join(preferences.interests)}

Available attractions:
{attractions_text}

Requirements:
- Use only attractions from the provided list.
- Do not invent new attractions.
- Do not repeat the same attraction on multiple days.
- Distribute activities across the requested number of days.
- Adjust the number of activities per day to the travel pace.
- Do not invent travel times, distances, opening hours, or prices.
- Keep source_indices exactly as provided for each attraction.
- Return exactly {preferences.duration_days} days.
- Number days sequentially starting from 1.
- If there are too few attractions, leave some days with empty activities.
- Return valid JSON only, without Markdown fences.

JSON structure:
{{
  "destination": "{preferences.destination}",
  "days": [
    {{
      "day": 1,
      "activities": [
        {{
          "name": "Attraction name",
          "description": "Short activity description",
          "source_indices": [1]
        }}
      ]
    }}
  ]
}}
"""

    response_text = await generate_text(prompt)

    
    try:
        trip = TravelItinerary.model_validate(json.loads(response_text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("The model returned an invalid trip plan.") from exc

    expected_days = list(range(1, preferences.duration_days + 1))
    actual_days = [day.day for day in trip.days]

    if actual_days != expected_days:
        raise ValueError(
            "The trip plan does not match the requested number of days."
        )

    allowed_attractions = {
        recommendation["name"].strip().casefold(): recommendation["source_indices"]
        for recommendation in recommendations
    }

    seen_names = set()

    for day in trip.days:
        for activity in day.activities:
            name = activity.name.strip().casefold()

            if name not in allowed_attractions:
                raise ValueError(
                    f"The trip plan contains an unknown attraction: {activity.name}"
                )

            if name in seen_names:
                raise ValueError(
                    f"The trip plan contains a duplicate attraction: {activity.name}"
                )

            if activity.source_indices != allowed_attractions[name]:
              raise ValueError(f"The trip plan contains incorrect sources for: {activity.name}")
              
            seen_names.add(name)
    return trip

