from datetime import datetime, timedelta

import httpx

from app.google_places import (
    OpeningHoursPeriod,
    get_place_opening_hours,
)
from app.schemas import TravelItinerary


def is_within_opening_hours(
    visit_start: datetime,
    visit_end: datetime,
    periods: list[OpeningHoursPeriod],
) -> bool:
    """Check whether a visit fits entirely inside one weekly opening period."""
    week_start = visit_start - timedelta(
        days=(visit_start.weekday() + 1) % 7,
        hours=visit_start.hour,
        minutes=visit_start.minute,
        seconds=visit_start.second,
        microseconds=visit_start.microsecond,
    )

    for period in periods:
        opening = period.open
        closing = period.close

        if closing is None:
            if opening.day == 0 and opening.hour == 0 and opening.minute == 0:
                return True
            continue

        start_offset = opening.day * 1440 + opening.hour * 60 + opening.minute
        end_offset = closing.day * 1440 + closing.hour * 60 + closing.minute

        if end_offset <= start_offset:
            end_offset += 7 * 1440

        for week_offset in (-7, 0, 7):
            period_start = week_start + timedelta(
                minutes=start_offset,
                days=week_offset,
            )
            period_end = week_start + timedelta(
                minutes=end_offset,
                days=week_offset,
            )

            if period_start <= visit_start and visit_end <= period_end:
                return True

    return False


def find_next_opening_slot(
    earliest_start: datetime,
    duration_minutes: int,
    periods: list[OpeningHoursPeriod],
) -> datetime | None:
    """Find the earliest same-day start that fits regular opening hours."""
    if duration_minutes <= 0:
        return None

    latest_start = earliest_start.replace(
        hour=23,
        minute=59,
        second=0,
        microsecond=0,
    )

    candidate = earliest_start.replace(
        second=0,
        microsecond=0,
    )

    if candidate < earliest_start:
        candidate += timedelta(minutes=1)

    while candidate <= latest_start:
        end = candidate + timedelta(minutes=duration_minutes)

        if end.date() == earliest_start.date() and is_within_opening_hours(
            candidate, end, periods
        ):
            return candidate

        candidate += timedelta(minutes=1)

    return None


def find_next_valid_slot(
    earliest_start: datetime,
    duration_minutes: int,
    periods: list[OpeningHoursPeriod] | None,
    experience_start_time: str | None,
    experience_end_time: str | None,
) -> datetime | None:
    """Find the earliest same-day slot satisfying all known time windows."""
    if duration_minutes <= 0:
        return None

    if (experience_start_time is None and experience_end_time is not None) or (
        experience_start_time is not None and experience_end_time is None
    ):
        return None

    candidate = earliest_start.replace(
        second=0,
        microsecond=0,
    )

    if candidate < earliest_start:
        candidate += timedelta(minutes=1)

    day_end = datetime.combine(
        earliest_start.date() + timedelta(days=1),
        datetime.min.time(),
    )

    if experience_start_time is not None:
        window_start = datetime.combine(
            earliest_start.date(),
            datetime.strptime(experience_start_time, "%H:%M").time(),
        )
        window_end = datetime.combine(
            earliest_start.date(),
            datetime.strptime(experience_end_time, "%H:%M").time(),
        )

        if window_end <= window_start:
            window_end += timedelta(days=1)

        candidate = max(candidate, window_start)
    else:
        window_end = day_end

    while candidate + timedelta(minutes=duration_minutes) <= min(
        day_end,
        window_end,
    ):
        visit_end = candidate + timedelta(minutes=duration_minutes)

        if periods is None or is_within_opening_hours(
            candidate,
            visit_end,
            periods,
        ):
            return candidate

        candidate += timedelta(minutes=1)

    return None


async def validate_itinerary_opening_hours(
    trip: TravelItinerary,
) -> TravelItinerary:
    """Compare scheduled visits against regular Google Places opening hours."""
    cache = {}

    for day in trip.days:
        for activity in day.activities:
            activity.opening_hours_status = "unknown"

            if (
                day.date is None
                or activity.start_time is None
                or activity.end_time is None
                or not activity.google_place_id
            ):
                continue

            try:
                visit_start = datetime.combine(
                    day.date,
                    datetime.strptime(activity.start_time, "%H:%M").time(),
                )
                visit_end = datetime.combine(
                    day.date,
                    datetime.strptime(activity.end_time, "%H:%M").time(),
                )

                if visit_end <= visit_start:
                    visit_end += timedelta(days=1)

                place_id = activity.google_place_id

                if place_id not in cache:
                    cache[place_id] = await get_place_opening_hours(place_id)

                periods = cache[place_id].periods

                if periods is None:
                    continue

                activity.opening_hours_status = (
                    "verified"
                    if is_within_opening_hours(
                        visit_start,
                        visit_end,
                        periods,
                    )
                    else "conflict"
                )

            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
            ):
                continue

    return trip
