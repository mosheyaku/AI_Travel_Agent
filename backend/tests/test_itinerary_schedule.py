from unittest.mock import AsyncMock

import pytest

from app import itinerary_schedule
from app.schemas import TravelItinerary
from types import SimpleNamespace

from app.location_validation import LocationStatus

def make_trip(duration_types):
    return TravelItinerary.model_validate({
        "destination": "Chiang Mai, Thailand",
        "days": [{
            "day": 1,
            "activities": [
                {
                    "name": f"Activity {index}",
                    "activity_type": "hiking",
                    "description": "Test activity",
                    "source_indices": [1],
                    "duration_type": duration_type,
                }
                for index, duration_type in enumerate(
                    duration_types, start=1
                )
            ],
        }],
    })


@pytest.mark.anyio
async def test_schedules_known_duration():
    trip = make_trip(["short"])

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    activity = result.days[0].activities[0]

    assert activity.start_time == "09:00"
    assert activity.end_time == "10:30"
    assert activity.estimated_duration_minutes == 90


@pytest.mark.anyio
async def test_unknown_duration_stops_schedule():
    trip = make_trip(["unknown", "short"])

    result = await itinerary_schedule.add_itinerary_schedule(trip)

    first, second = result.days[0].activities

    assert first.start_time is None
    assert first.end_time is None
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

    mock_route = AsyncMock(
        return_value=SimpleNamespace(duration_minutes=30)
    )

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