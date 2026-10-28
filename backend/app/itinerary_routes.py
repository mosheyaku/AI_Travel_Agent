import httpx

from app.google_routes import get_driving_route
from app.location_validation import LocationStatus
from app.schemas import ItineraryActivity, TravelItinerary
MAX_DAILY_DRIVING_MINUTES = 90

def has_verified_location(activity: ItineraryActivity) -> bool:
    """Check whether an activity has a verified Google location."""
    return (
        activity.location_status == LocationStatus.VERIFIED
        and activity.latitude is not None
        and activity.longitude is not None
        and activity.google_place_id is not None
    )


async def add_driving_routes(trip: TravelItinerary) -> TravelItinerary:
    """Add driving totals between consecutive activities in each day."""

    for day in trip.days:
        if len(day.activities) < 2:
            continue

        total_distance = 0.0
        total_minutes = 0
        all_routes_available = True

        for origin, destination in zip(
            day.activities,
            day.activities[1:],
        ):
            if not (
                has_verified_location(origin)
                and has_verified_location(destination)
            ):
                all_routes_available = False
                break

            try:
                route = await get_driving_route(
                    origin.latitude,
                    origin.longitude,
                    destination.latitude,
                    destination.longitude,
                )
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                all_routes_available = False
                break

            if route is None:
                all_routes_available = False
                break

            total_distance += route.distance_km
            total_minutes += route.duration_minutes

        if all_routes_available:
            day.driving_distance_km = round(total_distance, 1)
            day.driving_duration_minutes = total_minutes

    return trip


def find_driving_issues(
    trip: TravelItinerary,
    max_minutes: int = MAX_DAILY_DRIVING_MINUTES,
) -> list[str]:
    """Find days with excessive driving between attractions."""
    issues = []

    for day in trip.days:
        duration = day.driving_duration_minutes

        if duration is not None and duration > max_minutes:
            issues.append(
                f"Day {day.day}: driving between attractions "
                f"takes {duration} minutes, exceeding "
                f"the {max_minutes}-minute planning limit."
            )

    return issues