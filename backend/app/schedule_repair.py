from itertools import permutations

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


def count_timing_conflicts(trip: TravelItinerary) -> int:
    """Count activities that cannot fit their experience windows."""
    return sum(
        activity.timing_status == "conflict"
        for day in trip.days
        for activity in day.activities
    )


def count_schedule_conflicts(trip: TravelItinerary) -> int:
    """Count all known scheduling conflicts."""
    return count_opening_hours_conflicts(trip) + count_timing_conflicts(trip)


async def rebuild_schedule(
    trip: TravelItinerary,
    origin: tuple[float, float] | None = None,
    start_time: str = "09:00",
) -> TravelItinerary | None:
    """Rebuild routes and schedule while preserving route constraints."""
    await add_driving_routes(trip)

    if origin is not None:
        await add_total_driving_routes(
            trip,
            origin_latitude=origin[0],
            origin_longitude=origin[1],
        )

    if find_driving_issues(trip):
        return None

    await add_itinerary_schedule(
        trip,
        start_time=start_time,
        origin=origin,
    )
    await validate_itinerary_opening_hours(trip)

    return trip


async def repair_opening_hours_conflicts(
    trip: TravelItinerary,
    origin: tuple[float, float] | None = None,
    start_time: str = "09:00",
) -> TravelItinerary:
    """Try alternative activity orders to reduce scheduling conflicts."""
    best_trip = trip.model_copy(deep=True)
    best_conflicts = count_schedule_conflicts(best_trip)

    if best_conflicts == 0:
        return best_trip

    for day_index, day in enumerate(best_trip.days):
        if len(day.activities) < 2:
            continue

        if not any(
            activity.opening_hours_status == "conflict"
            or activity.timing_status == "conflict"
            for activity in day.activities
        ):
            continue

        original_order = tuple(range(len(day.activities)))

        for order in permutations(original_order):
            if order == original_order:
                continue

            candidate = best_trip.model_copy(deep=True)
            activities = candidate.days[day_index].activities

            candidate.days[day_index].activities = [
                activities[index] for index in order
            ]

            candidate = await rebuild_schedule(
                candidate,
                origin=origin,
                start_time=start_time,
            )

            if candidate is None:
                continue

            candidate_conflicts = count_schedule_conflicts(candidate)

            if candidate_conflicts < best_conflicts:
                best_trip = candidate
                best_conflicts = candidate_conflicts

            if best_conflicts == 0:
                return best_trip

    return best_trip


async def remove_unschedulable_activities(
    trip: TravelItinerary,
    origin: tuple[float, float] | None = None,
    start_time: str = "09:00",
) -> TravelItinerary:
    """Remove conflicting activities while preserving valid routes."""
    result = trip.model_copy(deep=True)
    max_removals = sum(len(day.activities) for day in result.days)

    for _ in range(max_removals):
        conflicts = [
            (day_index, activity_index)
            for day_index, day in enumerate(result.days)
            for activity_index, activity in enumerate(day.activities)
            if activity.opening_hours_status == "conflict"
            or activity.timing_status == "conflict"
        ]

        if not conflicts:
            return result

        best_candidate = None
        best_conflicts = float("inf")

        for day_index, activity_index in conflicts:
            candidate = result.model_copy(deep=True)
            del candidate.days[day_index].activities[activity_index]

            candidate = await rebuild_schedule(
                candidate,
                origin=origin,
                start_time=start_time,
            )

            if candidate is None:
                continue

            remaining_conflicts = count_schedule_conflicts(candidate)

            if remaining_conflicts < best_conflicts:
                best_candidate = candidate
                best_conflicts = remaining_conflicts

        if best_candidate is None:
            raise ValueError(
                "Could not rebuild a valid route after removing "
                "any conflicting activity."
            )

        result = best_candidate

    return result


async def fill_empty_days(
    trip: TravelItinerary,
    origin: tuple[float, float] | None = None,
    start_time: str = "09:00",
) -> TravelItinerary:
    """Move existing activities to empty days when the schedule remains valid."""
    result = trip.model_copy(deep=True)

    for empty_day_index, day in enumerate(result.days):
        if day.activities:
            continue

        best_candidate = None
        best_donor_count = 0

        for donor_index, donor_day in enumerate(result.days):
            if donor_index == empty_day_index or len(donor_day.activities) <= 1:
                continue

            for activity_index in range(len(donor_day.activities)):
                candidate = result.model_copy(deep=True)

                activity = candidate.days[donor_index].activities.pop(activity_index)
                candidate.days[empty_day_index].activities.append(activity)

                candidate = await rebuild_schedule(
                    candidate,
                    origin=origin,
                    start_time=start_time,
                )

                if candidate is None or count_schedule_conflicts(candidate):
                    continue

                donor_count = len(candidate.days[donor_index].activities)

                if best_candidate is None or donor_count > best_donor_count:
                    best_candidate = candidate
                    best_donor_count = donor_count

        if best_candidate is not None:
            result = best_candidate

    return result
