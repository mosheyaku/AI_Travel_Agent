
import json

from pydantic import ValidationError

from app.attraction_clustering import (
    MAX_CLUSTER_DISTANCE_KM,
    build_attraction_clusters,
)
from app.itinerary_distances import (
    build_attraction_distances,
    calculate_day_max_distance,
)
from app.llm import generate_text
from app.location_validation import LocationStatus
from app.schemas import TravelItinerary, TravelPreferences


MAX_GENERATION_ATTEMPTS = 2


def validate_trip_plan(
    trip: TravelItinerary,
    preferences: TravelPreferences,
    recommendations: list[dict],
) -> None:
    """Validate the itinerary and restore trusted attraction data."""
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


def find_geographic_issues(
    trip: TravelItinerary,
    max_distance_km: float = MAX_CLUSTER_DISTANCE_KM,
) -> list[str]:
    """Find days with verified attractions that are too far apart."""
    issues = []

    for day in trip.days:
        verified_activities = [
            activity
            for activity in day.activities
            if activity.location_status == LocationStatus.VERIFIED
            and activity.latitude is not None
            and activity.longitude is not None
            and activity.google_place_id
        ]

        if len(verified_activities) < 2:
            continue

        verified_day = day.model_copy(
            update={"activities": verified_activities}
        )
        distance = calculate_day_max_distance(verified_day)

        if distance is not None and distance > max_distance_km:
            names = ", ".join(
                activity.name for activity in verified_activities
            )
            issues.append(
                f"Day {day.day}: {names} "
                f"are spread across {distance} km straight-line."
            )

    return issues


async def generate_trip_plan(
    preferences: TravelPreferences,
    recommendations: list[dict],
) -> TravelItinerary:
    """Generate and geographically validate a daily trip plan."""
    attractions_text = json.dumps(
        recommendations,
        ensure_ascii=False,
    )

    distances = build_attraction_distances(recommendations)
    distances_text = json.dumps(distances, ensure_ascii=False)

    clusters = build_attraction_clusters(recommendations)
    clusters_text = json.dumps(clusters, ensure_ascii=False)

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

Suggested geographic attraction groups:
{clusters_text}

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
- Prefer attractions from the same geographic group on the same day.
- Do not combine verified attractions more than {MAX_CLUSTER_DISTANCE_KM} km apart
  (straight-line distance) on the same day.
- Attractions without verified locations are not part of geographic groups.
- Do not assume their locations or distances.
- Geographic groups are planning suggestions, not mandatory activity bundles.
- Do not invent driving times or travel distances.
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

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        response_text = await generate_text(prompt)

        try:
            trip = TravelItinerary.model_validate(
                json.loads(response_text)
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(
                "The model returned an invalid trip plan."
            ) from exc

        validate_trip_plan(trip, preferences, recommendations)

        issues = find_geographic_issues(trip)

        if not issues:
            return trip

        if attempt == MAX_GENERATION_ATTEMPTS - 1:
            raise ValueError(
                "The trip plan failed geographic validation: "
                + "; ".join(issues)
            )

        prompt += (
            "\n\nThe previous itinerary had geographic problems:\n"
            + "\n".join(issues)
            + "\nGenerate a corrected itinerary."
            + "\nKeep verified attractions within "
            + f"{MAX_CLUSTER_DISTANCE_KM} km straight-line "
            + "of one another when scheduled on the same day."
            + "\nReturn the complete corrected JSON itinerary."
        )

    raise ValueError("Failed to generate a valid trip plan.")
