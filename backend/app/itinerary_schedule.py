from datetime import datetime, timedelta

import httpx

from app.google_routes import get_driving_route
from app.itinerary_routes import has_verified_location
from app.schemas import TravelItinerary


ESTIMATED_DURATIONS = {
    "short": 90,
    "half_day": 240,
    "full_day": 480,
}


async def add_itinerary_schedule(
    trip: TravelItinerary,
    start_time: str = "09:00",
) -> TravelItinerary:
    """Add estimated activity times when durations and routes are known."""
    day_start = datetime.strptime(start_time, "%H:%M")

    for day in trip.days:
        current_time = day_start
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
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    schedule_available = False
                    previous_activity = activity
                    continue

                if route is None:
                    schedule_available = False
                    previous_activity = activity
                    continue

                activity.travel_minutes_from_previous = (
                    route.duration_minutes
                )

                current_time += timedelta(
                    minutes=route.duration_minutes
                )

            activity.start_time = current_time.strftime("%H:%M")

            current_time += timedelta(minutes=duration)

            activity.end_time = current_time.strftime("%H:%M")
            previous_activity = activity

    return trip