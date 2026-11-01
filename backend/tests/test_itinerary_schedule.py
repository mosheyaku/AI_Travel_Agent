from unittest.mock import AsyncMock

import pytest

from app import itinerary_schedule
from app.schemas import TravelItinerary
from types import SimpleNamespace
from datetime import date

from app.location_validation import LocationStatus
from app.google_places import OpeningHoursPeriod
from app.opening_hours_validation import find_next_valid_slot


def make_trip(duration_types):
    return TravelItinerary.model_validate(
        {
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": f"Activity {index}",
                            "activity_type": "hiking",
                            "description": "Test activity",
                            "source_indices": [1],
                            "duration_type": duration_type,
                        }
                        for index, duration_type in enumerate(duration_types, start=1)
                    ],
                }
            ],
        }
    )


@pytest.mark.anyio
async def test_schedules_known_duration():
    trip = make_trip(["short"])

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    activity = result.days[0].activities[0]

    assert activity.start_time == "09:00"
    assert activity.end_time == "10:30"
    assert activity.estimated_duration_minutes == 90
    assert activity.timing_status == "estimated"
    assert activity.schedule_status == "estimated"


@pytest.mark.anyio
async def test_unknown_duration_uses_default_and_continues_schedule():
    trip = make_trip(["unknown", "short"])

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    first, second = result.days[0].activities

    assert first.start_time == "09:00"
    assert first.end_time == "11:00"
    assert first.estimated_duration_minutes == 120

    assert second.estimated_duration_minutes == 90
    assert second.start_time is None
    assert second.end_time is None


@pytest.mark.anyio
async def test_unknown_route_stops_schedule(monkeypatch):
    trip = make_trip(["short", "short"])

    mock_route = AsyncMock()
    monkeypatch.setattr(
        itinerary_schedule,
        "get_driving_route",
        mock_route,
    )

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    first, second = result.days[0].activities

    assert first.start_time == "09:00"
    assert second.start_time is None
    mock_route.assert_not_awaited()


@pytest.mark.anyio
async def test_schedule_includes_verified_driving_time(monkeypatch):
    trip = make_trip(["short", "half_day"])
    first, second = trip.days[0].activities

    first.location_status = LocationStatus.VERIFIED
    first.latitude = 18.79
    first.longitude = 98.98
    first.google_place_id = "place-1"

    second.location_status = LocationStatus.VERIFIED
    second.latitude = 18.85
    second.longitude = 99.02
    second.google_place_id = "place-2"

    mock_route = AsyncMock(return_value=SimpleNamespace(duration_minutes=30))

    monkeypatch.setattr(
        itinerary_schedule,
        "get_driving_route",
        mock_route,
    )

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    first, second = result.days[0].activities

    assert first.start_time == "09:00"
    assert first.end_time == "10:30"

    assert second.travel_minutes_from_previous == 30
    assert second.start_time == "11:00"
    assert second.end_time == "15:00"

    mock_route.assert_awaited_once_with(
        18.79,
        98.98,
        18.85,
        99.02,
    )


def test_add_itinerary_dates():
    trip = make_trip(["short"])
    trip.days[0].day = 3

    result = itinerary_schedule.add_itinerary_dates(
        trip,
        date(2026, 12, 15),
    )

    assert result.days[0].date == date(2026, 12, 17)


def test_add_itinerary_dates_without_start_date():
    trip = make_trip(["short"])

    result = itinerary_schedule.add_itinerary_dates(
        trip,
        None,
    )

    assert result.days[0].date is None


def set_verified_location(activity, place_id, latitude, longitude):
    activity.location_status = LocationStatus.VERIFIED
    activity.google_place_id = place_id
    activity.latitude = latitude
    activity.longitude = longitude


@pytest.mark.anyio
async def test_unknown_duration_continues_schedule_with_verified_route(monkeypatch):
    trip = make_trip(["unknown", "short"])
    first, second = trip.days[0].activities

    set_verified_location(first, "place-1", 18.79, 98.98)
    set_verified_location(second, "place-2", 18.85, 99.02)

    mock_route = AsyncMock(return_value=SimpleNamespace(duration_minutes=30))

    monkeypatch.setattr(
        itinerary_schedule,
        "get_driving_route",
        mock_route,
    )

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    first, second = result.days[0].activities

    assert first.estimated_duration_minutes == 120
    assert first.start_time == "09:00"
    assert first.end_time == "11:00"

    assert second.travel_minutes_from_previous == 30
    assert second.estimated_duration_minutes == 90
    assert second.start_time == "11:30"
    assert second.end_time == "13:00"

    mock_route.assert_awaited_once_with(
        18.79,
        98.98,
        18.85,
        99.02,
    )


@pytest.mark.anyio
async def test_schedule_waits_until_place_opens(monkeypatch):
    trip = make_trip(["short"])
    trip.days[0].date = date(2026, 12, 15)

    activity = trip.days[0].activities[0]

    set_verified_location(
        activity,
        "place-1",
        18.79,
        98.98,
    )

    mock_hours = AsyncMock(
        return_value=SimpleNamespace(
            periods=[
                OpeningHoursPeriod.model_validate(
                    {
                        "open": {"day": 2, "hour": 11},
                        "close": {"day": 2, "hour": 17},
                    }
                )
            ]
        )
    )

    monkeypatch.setattr(
        itinerary_schedule,
        "get_place_opening_hours",
        mock_hours,
    )

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    activity = result.days[0].activities[0]

    assert activity.start_time == "11:00"
    assert activity.end_time == "12:30"

    mock_hours.assert_awaited_once_with("place-1")


@pytest.mark.anyio
async def test_delayed_activity_shifts_next_activity(monkeypatch):
    trip = make_trip(["short", "short"])
    trip.days[0].date = date(2026, 12, 15)

    first, second = trip.days[0].activities

    set_verified_location(first, "place-1", 18.79, 98.98)
    set_verified_location(second, "place-2", 18.85, 99.02)

    async def mock_opening_hours(place_id):
        if place_id == "place-1":
            return SimpleNamespace(
                periods=[
                    OpeningHoursPeriod.model_validate(
                        {
                            "open": {"day": 2, "hour": 11},
                            "close": {"day": 2, "hour": 17},
                        }
                    )
                ]
            )

        return SimpleNamespace(periods=None)

    monkeypatch.setattr(
        itinerary_schedule,
        "get_place_opening_hours",
        mock_opening_hours,
    )

    mock_route = AsyncMock(return_value=SimpleNamespace(duration_minutes=30))

    monkeypatch.setattr(
        itinerary_schedule,
        "get_driving_route",
        mock_route,
    )

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    first, second = result.days[0].activities

    assert first.start_time == "11:00"
    assert first.end_time == "12:30"

    assert second.travel_minutes_from_previous == 30
    assert second.start_time == "13:00"
    assert second.end_time == "14:30"


@pytest.mark.anyio
async def test_schedule_preserves_conflict_when_no_slot_exists(monkeypatch):
    trip = make_trip(["half_day"])
    trip.days[0].date = date(2026, 12, 15)

    activity = trip.days[0].activities[0]

    set_verified_location(activity, "place-1", 18.79, 98.98)

    mock_hours = AsyncMock(
        return_value=SimpleNamespace(
            periods=[
                OpeningHoursPeriod.model_validate(
                    {
                        "open": {"day": 2, "hour": 9},
                        "close": {"day": 2, "hour": 12},
                    }
                )
            ]
        )
    )

    monkeypatch.setattr(
        itinerary_schedule,
        "get_place_opening_hours",
        mock_hours,
    )

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    activity = result.days[0].activities[0]

    assert activity.start_time is None
    assert activity.end_time is None
    assert activity.estimated_duration_minutes == 240
    assert activity.timing_status == "conflict"
    assert activity.schedule_status == "unknown"


@pytest.mark.anyio
async def test_schedule_includes_accommodation_departure_and_return(monkeypatch):
    trip = make_trip(["short"])
    activity = trip.days[0].activities[0]

    set_verified_location(activity, "place-1", 18.79, 98.98)

    mock_route = AsyncMock(
        side_effect=[
            SimpleNamespace(duration_minutes=45),
            SimpleNamespace(duration_minutes=35),
        ]
    )

    monkeypatch.setattr(
        itinerary_schedule,
        "get_driving_route",
        mock_route,
    )

    result = await itinerary_schedule.add_itinerary_schedule(
        trip,
        origin=(18.78, 98.99),
    )

    day = result.days[0]

    assert activity.start_time == "09:00"
    assert activity.end_time == "10:30"
    assert day.departure_time == "08:15"
    assert day.return_time == "11:05"
    assert day.travel_minutes_to_first == 45
    assert day.travel_minutes_to_accommodation == 35

    assert mock_route.await_count == 2


@pytest.mark.anyio
async def test_schedule_without_origin_keeps_accommodation_times_unknown():
    trip = make_trip(["short"])

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    day = result.days[0]

    assert day.departure_time is None
    assert day.return_time is None
    assert day.travel_minutes_to_first is None
    assert day.travel_minutes_to_accommodation is None


@pytest.mark.anyio
async def test_schedule_prefers_exact_duration_over_duration_type():
    trip = make_trip(["short"])
    activity = trip.days[0].activities[0]

    activity.duration_minutes = 120

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    activity = result.days[0].activities[0]

    assert activity.duration_type == "short"
    assert activity.duration_minutes == 120
    assert activity.estimated_duration_minutes == 120

    assert activity.start_time == "09:00"
    assert activity.end_time == "11:00"


@pytest.mark.anyio
async def test_guided_tour_schedule_is_estimated():
    trip = make_trip(["half_day"])
    activity = trip.days[0].activities[0]

    activity.booking_type = "guided_tour"
    activity.duration_minutes = 180

    await itinerary_schedule.add_itinerary_schedule(trip)

    assert activity.start_time == "09:00"
    assert activity.end_time == "12:00"
    assert activity.estimated_duration_minutes == 180
    assert activity.schedule_status == "estimated"


@pytest.mark.anyio
async def test_guided_tour_requires_booking_confirmation():
    from app.schemas import TravelItinerary
    from app.itinerary_schedule import add_itinerary_schedule

    trip = TravelItinerary.model_validate(
        {
            "destination": "Chiang Mai",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Elephant Sanctuary Tour",
                            "activity_type": "elephant_sanctuary",
                            "description": "Guided visit.",
                            "source_indices": [1],
                            "booking_type": "guided_tour",
                            "duration_type": "half_day",
                        }
                    ],
                }
            ],
        }
    )

    result = await add_itinerary_schedule(trip)
    activity = result.days[0].activities[0]

    assert activity.schedule_status == "estimated"
    assert activity.timing_status == "requires_booking_confirmation"


from datetime import datetime

from app.opening_hours_validation import find_next_valid_slot


def test_experience_slot_waits_until_evening():
    earliest = datetime(2026, 11, 8, 11, 0)

    result = find_next_valid_slot(
        earliest_start=earliest,
        duration_minutes=120,
        periods=None,
        experience_start_time="18:00",
        experience_end_time="22:00",
    )

    assert result == datetime(2026, 11, 8, 18, 0)


def test_experience_slot_rejects_insufficient_time():
    earliest = datetime(2026, 11, 8, 21, 0)

    result = find_next_valid_slot(
        earliest_start=earliest,
        duration_minutes=120,
        periods=None,
        experience_start_time="18:00",
        experience_end_time="22:00",
    )

    assert result is None
