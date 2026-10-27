from app.location_validation import calculate_distance_km, LocationStatus
from app.schemas import ItineraryDay


def calculate_day_max_distance(day: ItineraryDay) -> float | None:
    """Return the maximum straight-line distance between activities in a day."""
    locations = [
        activity
        for activity in day.activities
        if activity.latitude is not None
        and activity.longitude is not None
    ]

    if len(locations) < 2:
        return None

    max_distance = 0.0

    for i, first in enumerate(locations):
        for second in locations[i + 1:]:
            distance = calculate_distance_km(
                first.latitude,
                first.longitude,
                second.latitude,
                second.longitude,
            )
            max_distance = max(max_distance, distance)

    return round(max_distance, 1)


def build_attraction_distances(
    recommendations: list[dict],
) -> list[dict]:
    """Calculate straight-line distances between located attractions."""
    located = [
        recommendation
        for recommendation in recommendations
        if recommendation.get("location_status") == LocationStatus.VERIFIED
        and recommendation.get("latitude") is not None
        and recommendation.get("longitude") is not None
        and recommendation.get("google_place_id")
    ]

    distances = []

    for i, first in enumerate(located):
        for second in located[i + 1:]:
            distance = calculate_distance_km(
                first["latitude"],
                first["longitude"],
                second["latitude"],
                second["longitude"],
            )

            distances.append({
                "from": first["name"],
                "to": second["name"],
                "distance_km": round(distance, 1),
            })

    return distances