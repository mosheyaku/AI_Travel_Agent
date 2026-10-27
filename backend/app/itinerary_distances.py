from app.location_validation import calculate_distance_km
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