import json

from pydantic import ValidationError

from app.llm import generate_text
from app.location_validation import LocationStatus
from app.schemas import TravelItinerary, TravelPreferences
from app.itinerary_distances import calculate_day_max_distance, build_attraction_distances


async def generate_trip_plan(
    preferences: TravelPreferences,
    recommendations: list[dict],
) -> TravelItinerary:
    """Generate a daily trip plan from attraction recommendations."""
    attractions_text = json.dumps(recommendations, ensure_ascii=False)

    distances = build_attraction_distances(recommendations)
    distances_text = json.dumps(distances, ensure_ascii=False)

    prompt = f"""
You are a travel planning assistant.

Create a {preferences.duration_days}-day trip plan for
{preferences.destination}.

Travel pace: {preferences.pace}
User interests: {", ".join(preferences.interests)}

Available attractions:
{attractions_text}

Straight-line distances between verified attractions (km):
{distances_text}

Requirements:
- Use only attractions from the provided list.
- Do not invent new attractions.
- Preserve attraction names exactly as provided.
- Do not repeat the same attraction on multiple days.
- Prioritize attractions that match the user's interests.
- Include a variety of activities across the requested interests.
- Avoid selecting multiple attractions that offer essentially the same experience.
- Do not schedule multiple elephant sanctuary visits unless explicitly requested.
- Do not schedule two full-day or long guided tours on the same day.
- Prefer 1-2 substantial activities per day for a relaxed pace.
- Prefer 2-3 activities per day for a balanced pace.
- Prefer 3-4 activities per day for an active pace, only when realistically feasible.
- A full-day activity may occupy an entire day regardless of pace.
- Distribute activities across the requested number of days.
- Do not invent travel times, distances, opening hours, durations, or prices.
- Keep source_indices exactly as provided for each attraction.
- Return exactly {preferences.duration_days} days.
- Number days sequentially starting from 1.
- If there are too few suitable attractions, leave some days with fewer or no activities.
- Return valid JSON only, without Markdown fences.
- Prefer grouping geographically close attractions on the same day.
- Avoid combining distant attractions when closer alternatives are available.
- Distances are straight-line estimates, not driving distances or travel times.
- Do not invent distances for attractions without verified coordinates.

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
        recommendation["name"].strip().casefold(): recommendation
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

            original = allowed_attractions[name]

            if activity.source_indices != original["source_indices"]:
                raise ValueError(
                    f"The trip plan contains incorrect sources for: {activity.name}"
                )

            activity.name = original["name"]
            activity.location_status = original.get(
                "location_status",
                LocationStatus.UNVERIFIED,
            )
            activity.latitude = original.get("latitude")
            activity.longitude = original.get("longitude")
            activity.google_place_id = original.get("google_place_id")

            seen_names.add(name)

    for day in trip.days:
        day.max_distance_km = calculate_day_max_distance(day)

    return trip
