from app.itinerary_routes import (
    add_driving_routes,
    add_total_driving_routes,
    find_driving_issues,
    find_total_driving_issues,
)
from app.itinerary_schedule import add_itinerary_schedule
from app.opening_hours_validation import validate_itinerary_opening_hours
from app.schemas import TravelItinerary


def count_opening_hours_conflicts(trip: TravelItinerary) -> int:
    """Count activities with conflicting opening hours."""
    return sum(
        activity.opening_hours_status == "conflict"
        for day in trip.days
        for activity in day.activities
    )


async def repair_opening_hours_conflicts(
    trip: TravelItinerary,
    origin: tuple[float, float] | None = None,
) -> TravelItinerary:
    """Try swapping two activities to reduce opening-hours conflicts."""
    best_trip = trip.model_copy(deep=True)
    best_conflicts = count_opening_hours_conflicts(best_trip) + count_timing_conflicts(
        best_trip
    )

    if best_conflicts == 0:
        return best_trip

    for day_index, day in enumerate(trip.days):
        if len(day.activities) != 2:
            continue

        if not any(
            activity.opening_hours_status == "conflict"
            or activity.timing_status == "conflict"
            for activity in day.activities
        ):
            continue

        candidate = best_trip.model_copy(deep=True)
        candidate.days[day_index].activities.reverse()

        await add_itinerary_schedule(candidate, origin=origin)
        await validate_itinerary_opening_hours(candidate)
        await add_driving_routes(candidate)

        if origin is not None:
            await add_total_driving_routes(
                candidate,
                origin_latitude=origin[0],
                origin_longitude=origin[1],
            )

        if find_driving_issues(candidate) or find_total_driving_issues(candidate):
            continue

        candidate_conflicts = count_opening_hours_conflicts(
            candidate
        ) + count_timing_conflicts(candidate)

        if candidate_conflicts < best_conflicts:
            best_trip = candidate
            best_conflicts = candidate_conflicts

    return best_trip


def count_timing_conflicts(trip: TravelItinerary) -> int:
    """Count activities that cannot fit their experience windows."""
    return sum(
        activity.timing_status == "conflict"
        for day in trip.days
        for activity in day.activities
    )
