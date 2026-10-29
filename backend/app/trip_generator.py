
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
from app.itinerary_routes import (
    MAX_DAILY_DRIVING_MINUTES,
    MAX_TOTAL_DAILY_DRIVING_MINUTES,
    add_driving_routes,
    find_driving_issues,
    add_total_driving_routes,
    find_total_driving_issues,
)
import httpx

from app.geocoding import search_locations
from app.attraction_locations import find_destination

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
            activity.activity_type = original["activity_type"]
            activity.location_status = original.get(
                "location_status",
                LocationStatus.UNVERIFIED,
            )
            activity.latitude = original.get("latitude")
            activity.longitude = original.get("longitude")
            activity.google_place_id = original.get("google_place_id")
            activity.duration_type = original.get("duration_type", "unknown")

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



def find_activity_load_issues(trip: TravelItinerary) -> list[str]:
    """Find days with incompatible activity durations."""
    issues = []

    for day in trip.days:
        full_day_activities = [
            activity.name
            for activity in day.activities
            if activity.duration_type == "full_day"
        ]

        if full_day_activities and len(day.activities) > 1:
            issues.append(
                f"Day {day.day}: full-day activity "
                f"({', '.join(full_day_activities)}) "
                "is scheduled with other activities."
            )
            continue

        half_day_activities = [
            activity.name
            for activity in day.activities
            if activity.duration_type == "half_day"
        ]

        if len(half_day_activities) > 2:
            issues.append(
                f"Day {day.day}: too many half-day activities "
                f"({', '.join(half_day_activities)})."
            )

    return issues

RESTRICTED_REPEATED_ACTIVITY_TYPES = {
    "elephant_sanctuary",
    "zipline",
    "rafting",
    "cooking_class",
    "water_park",
}


def find_repetitive_experience_issues(
    trip: TravelItinerary,
) -> list[str]:
    """Find repeated experiences that add little variety to a trip."""
    issues = []
    seen_types = {}

    for day in trip.days:
        for activity in day.activities:
            activity_type = activity.activity_type

            if activity_type not in RESTRICTED_REPEATED_ACTIVITY_TYPES:
                continue

            if activity_type in seen_types:
                previous_day, previous_name = seen_types[activity_type]

                issues.append(
                    f"Day {day.day}: {activity.name} repeats the "
                    f"{activity_type} experience already scheduled "
                    f"on Day {previous_day} ({previous_name})."
                )
            else:
                seen_types[activity_type] = (
                    day.day,
                    activity.name,
                )

    return issues


async def find_trip_origin(
    destination: str,
) -> tuple[float, float] | None:
    """Find an approximate starting point for the destination."""

    try:
        candidates = await search_locations(destination, "")
    except (httpx.HTTPError, TimeoutError):
        return None

    location = find_destination(destination, candidates)

    if location is None:
        return None

    return location.latitude, location.longitude


def total_trip_driving_minutes(trip: TravelItinerary) -> float:
    """Calculate total driving time, penalizing unknown durations."""
    return sum(
        day.total_driving_duration_minutes
        if day.total_driving_duration_minutes is not None
        else float("inf")
        for day in trip.days
        if day.activities
    )

def total_driving_excess_minutes(
    trip: TravelItinerary,
    max_minutes: int = MAX_TOTAL_DAILY_DRIVING_MINUTES,
) -> float:
    """Calculate total driving minutes exceeding the daily target."""
    return sum(
        max(0, day.total_driving_duration_minutes - max_minutes)
        if day.total_driving_duration_minutes is not None
        else float("inf")
        for day in trip.days
        if day.activities
    )


def reset_route_data(trip: TravelItinerary) -> None:
    """Discard route values after changing the itinerary."""
    for day in trip.days:
        day.max_distance_km = calculate_day_max_distance(day)
        day.driving_distance_km = None
        day.driving_duration_minutes = None
        day.driving_status = "unknown"
        day.total_driving_distance_km = None
        day.total_driving_duration_minutes = None


def find_planning_issues(trip: TravelItinerary) -> list[str]:
    """Find itinerary issues that do not require route API calls."""
    return (
        find_geographic_issues(trip)
        + find_activity_load_issues(trip)
        + find_repetitive_experience_issues(trip)
    )


async def repair_trip_plan(
    trip: TravelItinerary,
    preferences: TravelPreferences,
    recommendations: list[dict],
) -> TravelItinerary | None:
    """Repair an invalid itinerary using limited activity edits."""
    original_count = sum(len(day.activities) for day in trip.days)

    best: TravelItinerary | None = None
    best_score: tuple[int, int] | None = None
    checked = 0
    max_candidates = 80

    for source_index, source_day in enumerate(trip.days):
        for activity_index in range(len(source_day.activities)):
            destinations = [
                source_index,
                *(
                    index
                    for index in range(len(trip.days))
                    if index != source_index
                ),
                None,
            ]

            for destination_index in destinations:
                if destination_index == source_index:
                    positions = range(len(source_day.activities))
                elif destination_index is None:
                    positions = (0,)
                else:
                    positions = range(
                        len(trip.days[destination_index].activities) + 1
                    )

                for position in positions:
                    if (
                        destination_index == source_index
                        and position == activity_index
                    ):
                        continue

                    if checked >= max_candidates:
                        return best

                    checked += 1

                    candidate = trip.model_copy(deep=True)

                    activity = candidate.days[
                        source_index
                    ].activities.pop(activity_index)

                    if destination_index is not None:
                        candidate.days[
                            destination_index
                        ].activities.insert(position, activity)

                    reset_route_data(candidate)

                    if find_planning_issues(candidate):
                        continue

                    validate_trip_plan(
                        candidate,
                        preferences,
                        recommendations,
                    )

                    await add_driving_routes(candidate)

                    if find_driving_issues(candidate):
                        continue

                    if any(
                        len(day.activities) > 1
                        and day.driving_status != "verified"
                        for day in candidate.days
                    ):
                        continue

                    count = sum(
                        len(day.activities)
                        for day in candidate.days
                    )

                    minutes = sum(
                        day.driving_duration_minutes or 0
                        for day in candidate.days
                    )

                    score = (
                        original_count - count,
                        minutes,
                    )

                    if best_score is None or score < best_score:
                        best = candidate
                        best_score = score

                        if score == (0, 0):
                            return best

    return best


async def generate_trip_plan(
    preferences: TravelPreferences,
    recommendations: list[dict],
) -> TravelItinerary:
    """Generate and geographically validate a daily trip plan."""

    verified_recommendations = [
        recommendation
        for recommendation in recommendations
        if recommendation.get("location_status") == LocationStatus.VERIFIED
        and recommendation.get("latitude") is not None
        and recommendation.get("longitude") is not None
        and recommendation.get("google_place_id")
    ]

    if not verified_recommendations:
        raise ValueError(
            "No attractions with verified locations are available."
        )

    recommendations = verified_recommendations

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
- Preserve the activity_type of each attraction exactly as provided.
- Do not invent or modify activity_type values.
- Do not repeat the same attraction on multiple days.
- Prioritize attractions that match the user's interests.
- Maximize the variety of experiences across the entire trip.
- Prefer distinct activity types rather than different providers offering the same activity.
- For example, do not select two similar zipline experiences when one zipline
  experience could be combined with rafting, hiking, or a waterfall visit.
- Two attractions in the same broad category are acceptable when they offer
  meaningfully different experiences.
- Do not add repetitive activities merely to fill the requested daily pace.
- Prefer fewer meaningful activities over a larger number of repetitive ones.
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
- Prefer daily plans with no more than 90 minutes of driving between attractions.

JSON structure:
{{
  "destination": "{preferences.destination}",
  "days": [
    {{
      "day": 1,
      "activities": [
        {{
          "name": "Attraction name",
          "activity_type": "zipline",
          "description": "Short activity description",
          "source_indices": [1]
        }}
      ]
    }}
  ]
}}
"""

    fallback_trip = None

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

        geographic_issues = find_geographic_issues(trip)
        activity_issues = find_activity_load_issues(trip)
        repetition_issues = find_repetitive_experience_issues(trip)

        issues = geographic_issues + activity_issues + repetition_issues

        if not issues:
            trip = await add_driving_routes(trip)
            issues = find_driving_issues(trip)

        if not issues:
            origin = await find_trip_origin(preferences.destination)

            if origin is not None:
                trip = await add_total_driving_routes(
                    trip,
                    origin_latitude=origin[0],
                    origin_longitude=origin[1],
                )

                driving_issues = find_total_driving_issues(trip)

                if driving_issues:
                    # Long driving times are quality issues, not validation errors.
                    if (
                        fallback_trip is None
                        or (
                            total_driving_excess_minutes(trip),
                            total_trip_driving_minutes(trip),
                        )
                        < (
                            total_driving_excess_minutes(fallback_trip),
                            total_trip_driving_minutes(fallback_trip),
                        )
                    ):
                    
                        fallback_trip = trip

                    issues = driving_issues
                else:
                    return trip
            else:
                return trip

        if attempt == MAX_GENERATION_ATTEMPTS - 1:
            if fallback_trip is not None:
                return fallback_trip

            repaired = await repair_trip_plan(
                trip,
                preferences,
                recommendations,
            )
            
            if repaired is not None:
                origin = await find_trip_origin(preferences.destination)
                
                if origin is not None:
                    repaired = await add_total_driving_routes(
                        repaired,
                        origin_latitude=origin[0],
                        origin_longitude=origin[1],
                    )
                return repaired

            raise ValueError(
                "The trip plan failed route validation: "
                + "; ".join(issues)
            )

        prompt += (
            "\n\nThe previous itinerary had planning problems:\n"
            + "\n".join(issues)
            + "\nGenerate a corrected itinerary."
            + "\nFix the reported problems by changing the selected attractions, "
            + "their grouping, or their order as needed."
            + "\nDo not introduce repetitive experiences just to fill a day."
            + "\nUse only the provided attractions and preserve their "
            + "source indices."
            + "\nReturn the complete corrected JSON itinerary."
        )

    raise ValueError("Failed to generate a valid trip plan.")