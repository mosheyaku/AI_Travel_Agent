from datetime import datetime, timedelta, date

import httpx

from app.google_places import get_place_opening_hours
from app.google_routes import get_driving_route
from app.itinerary_routes import has_verified_location
from app.opening_hours_validation import find_next_valid_slot
from app.schemas import TravelItinerary


ESTIMATED_DURATIONS = {
    "short": 90,
    "half_day": 240,
    "full_day": 480,
}

DEFAULT_DURATION_MINUTES = 120
REFERENCE_SUNDAY = date(2026, 11, 1)


def get_candidate_dates(day_date: date | None) -> list[date]:
    """Return the actual date or one representative of each weekday."""
    if day_date is not None:
        return [day_date]

    return [REFERENCE_SUNDAY + timedelta(days=offset) for offset in range(7)]


async def add_itinerary_schedule(
    trip: TravelItinerary,
    start_time: str = "09:00",
    origin: tuple[float, float] | None = None,
) -> TravelItinerary:
    """Schedule activities using one consistent weekday per itinerary day."""
    day_start = datetime.strptime(start_time, "%H:%M").time()
    opening_hours_cache = {}
    route_cache = {}

    async def get_cached_route(
        start_latitude: float,
        start_longitude: float,
        end_latitude: float,
        end_longitude: float,
    ):
        key = (
            start_latitude,
            start_longitude,
            end_latitude,
            end_longitude,
        )

        if key not in route_cache:
            try:
                route_cache[key] = await get_driving_route(*key)
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
            ):
                route_cache[key] = None

        return route_cache[key]

    async def get_cached_opening_hours(place_id: str):
        if place_id not in opening_hours_cache:
            try:
                result = await get_place_opening_hours(place_id)
                opening_hours_cache[place_id] = result.periods
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
            ):
                opening_hours_cache[place_id] = None

        return opening_hours_cache[place_id]

    for day in trip.days:
        best_schedule = None
        best_score = None

        for candidate_date in get_candidate_dates(day.date):
            current_time = datetime.combine(candidate_date, day_start)
            previous_activity = None
            scheduled_activities = []
            conflicts = 0
            schedule_available = True

            for activity in day.activities:
                duration = (
                    activity.duration_minutes
                    if activity.duration_minutes is not None
                    else ESTIMATED_DURATIONS.get(
                        activity.duration_type,
                        DEFAULT_DURATION_MINUTES,
                    )
                )

                travel_minutes = None

                if not schedule_available:
                    scheduled_activities.append((None, None, duration, None, "unknown"))
                    continue

                if previous_activity is not None:
                    if not (
                        has_verified_location(previous_activity)
                        and has_verified_location(activity)
                    ):
                        schedule_available = False
                        scheduled_activities.append(
                            (None, None, duration, None, "unknown")
                        )
                        continue

                    route = await get_cached_route(
                        previous_activity.latitude,
                        previous_activity.longitude,
                        activity.latitude,
                        activity.longitude,
                    )

                    if route is None:
                        schedule_available = False
                        scheduled_activities.append(
                            (None, None, duration, None, "unknown")
                        )
                        continue

                    travel_minutes = route.duration_minutes
                    current_time += timedelta(minutes=travel_minutes)

                periods = None

                if activity.google_place_id:
                    periods = await get_cached_opening_hours(activity.google_place_id)

                valid_slot = find_next_valid_slot(
                    earliest_start=current_time,
                    duration_minutes=duration,
                    periods=periods,
                    experience_start_time=activity.experience_start_time,
                    experience_end_time=activity.experience_end_time,
                )

                if valid_slot is None:
                    conflicts += 1
                    schedule_available = False
                    scheduled_activities.append(
                        (None, None, duration, travel_minutes, "conflict")
                    )
                    continue

                visit_end = valid_slot + timedelta(minutes=duration)

                scheduled_activities.append(
                    (
                        valid_slot,
                        visit_end,
                        duration,
                        travel_minutes,
                        "estimated",
                    )
                )

                current_time = visit_end
                previous_activity = activity

            scheduled_count = sum(
                start is not None for start, _, _, _, _ in scheduled_activities
            )

            score = (
                -conflicts,
                scheduled_count,
                -current_time.hour * 60 - current_time.minute,
            )

            if best_score is None or score > best_score:
                best_score = score
                best_schedule = scheduled_activities

        day.departure_time = None
        day.return_time = None
        day.travel_minutes_to_first = None
        day.travel_minutes_to_accommodation = None

        for activity, schedule in zip(day.activities, best_schedule):
            start, end, duration, travel_minutes, status = schedule

            activity.start_time = start.strftime("%H:%M") if start is not None else None
            activity.end_time = end.strftime("%H:%M") if end is not None else None
            activity.estimated_duration_minutes = duration
            activity.travel_minutes_from_previous = travel_minutes
            activity.schedule_status = "unknown" if status == "conflict" else status

            if status == "conflict":
                activity.timing_status = "conflict"
            elif status == "unknown":
                activity.timing_status = "unknown"
            elif activity.booking_type in {
                "scheduled_activity",
                "guided_tour",
            }:
                activity.timing_status = "requires_booking_confirmation"
            else:
                activity.timing_status = "estimated"

        if origin is None or not day.activities:
            continue

        first = day.activities[0]
        last = day.activities[-1]

        if first.start_time is not None and has_verified_location(first):
            route = await get_cached_route(
                origin[0],
                origin[1],
                first.latitude,
                first.longitude,
            )

            if route is not None:
                first_start = datetime.combine(
                    day.date or REFERENCE_SUNDAY,
                    datetime.strptime(first.start_time, "%H:%M").time(),
                )

                departure = first_start - timedelta(minutes=route.duration_minutes)

                day.departure_time = departure.strftime("%H:%M")
                day.travel_minutes_to_first = route.duration_minutes

        if last.end_time is not None and has_verified_location(last):
            route = await get_cached_route(
                last.latitude,
                last.longitude,
                origin[0],
                origin[1],
            )

            if route is not None:
                last_end = datetime.combine(
                    day.date or REFERENCE_SUNDAY,
                    datetime.strptime(last.end_time, "%H:%M").time(),
                )

                returned = last_end + timedelta(minutes=route.duration_minutes)

                day.return_time = returned.strftime("%H:%M")
                day.travel_minutes_to_accommodation = route.duration_minutes

    return trip


def add_itinerary_dates(
    trip: TravelItinerary,
    start_date: date | None,
) -> TravelItinerary:
    """Assign calendar dates to itinerary days."""
    for day in trip.days:
        day.date = (
            start_date + timedelta(days=day.day - 1) if start_date is not None else None
        )

    return trip
