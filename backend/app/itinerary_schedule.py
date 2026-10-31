from datetime import datetime, timedelta, date

import httpx

from app.google_places import get_place_opening_hours
from app.google_routes import get_driving_route
from app.itinerary_routes import has_verified_location
from app.opening_hours_validation import find_next_opening_slot
from app.schemas import TravelItinerary


ESTIMATED_DURATIONS = {
    "short": 90,
    "half_day": 240,
    "full_day": 480,
}


async def add_itinerary_schedule(
    trip: TravelItinerary,
    start_time: str = "09:00",
    origin: tuple[float, float] | None = None,
) -> TravelItinerary:
    """Schedule activities, travel, and accommodation departure/return."""
    day_start = datetime.strptime(start_time, "%H:%M").time()
    opening_hours_cache = {}

    for day in trip.days:
        current_time = datetime.combine(
            day.date if day.date is not None else date.today(),
            day_start,
        )

        day.departure_time = None
        day.return_time = None
        day.travel_minutes_to_first = None
        day.travel_minutes_to_accommodation = None

        previous_activity = None
        schedule_available = True

        for activity in day.activities:
            activity.start_time = None
            activity.end_time = None
            activity.estimated_duration_minutes = None
            activity.travel_minutes_from_previous = None

            duration = ESTIMATED_DURATIONS.get(activity.duration_type)

            if duration is None:
                schedule_available = False
                previous_activity = activity
                continue

            activity.estimated_duration_minutes = duration

            if not schedule_available:
                previous_activity = activity
                continue

            if previous_activity is not None:
                if not (
                    has_verified_location(previous_activity)
                    and has_verified_location(activity)
                ):
                    schedule_available = False
                    previous_activity = activity
                    continue

                try:
                    route = await get_driving_route(
                        previous_activity.latitude,
                        previous_activity.longitude,
                        activity.latitude,
                        activity.longitude,
                    )
                except (
                    httpx.HTTPError,
                    ValueError,
                    KeyError,
                    TypeError,
                ):
                    schedule_available = False
                    previous_activity = activity
                    continue

                if route is None:
                    schedule_available = False
                    previous_activity = activity
                    continue

                activity.travel_minutes_from_previous = route.duration_minutes
                current_time += timedelta(minutes=route.duration_minutes)

            if day.date is not None and activity.google_place_id:
                try:
                    place_id = activity.google_place_id

                    if place_id not in opening_hours_cache:
                        opening_hours_cache[place_id] = await get_place_opening_hours(
                            place_id
                        )

                    periods = opening_hours_cache[place_id].periods

                    if periods is not None:
                        next_start = find_next_opening_slot(
                            current_time,
                            duration,
                            periods,
                        )

                        if next_start is not None:
                            current_time = next_start

                except (
                    httpx.HTTPError,
                    ValueError,
                    KeyError,
                    TypeError,
                ):
                    pass

            activity.start_time = current_time.strftime("%H:%M")
            current_time += timedelta(minutes=duration)
            activity.end_time = current_time.strftime("%H:%M")

            previous_activity = activity

        if origin is None or not day.activities:
            continue

        first = day.activities[0]
        last = day.activities[-1]

        if first.start_time is not None and has_verified_location(first):
            try:
                route = await get_driving_route(
                    origin[0],
                    origin[1],
                    first.latitude,
                    first.longitude,
                )
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
            ):
                route = None

            if route is not None:
                first_start = datetime.combine(
                    current_time.date(),
                    datetime.strptime(first.start_time, "%H:%M").time(),
                )

                departure = first_start - timedelta(minutes=route.duration_minutes)

                day.departure_time = departure.strftime("%H:%M")
                day.travel_minutes_to_first = route.duration_minutes

        if last.end_time is not None and has_verified_location(last):
            try:
                route = await get_driving_route(
                    last.latitude,
                    last.longitude,
                    origin[0],
                    origin[1],
                )
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
            ):
                route = None

            if route is not None:
                last_end = datetime.combine(
                    current_time.date(),
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
