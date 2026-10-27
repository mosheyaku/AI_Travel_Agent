import httpx
import pytest

from app import itinerary_routes
from app.google_routes import DrivingRoute
from app.schemas import TravelItinerary


def make_trip(activities):
    return TravelItinerary.model_validate({
        "destination": "Chiang Mai, Thailand",
        "days": [
            {
                "day": 1,
                "activities": activities,
            }
        ],
    })


def make_activity(name, latitude, longitude, verified=True):
    return {
        "name": name,
        "description": "Test attraction.",
        "source_indices": [1],
        "location_status": "verified" if verified else "unverified",
        "latitude": latitude,
        "longitude": longitude,
        "google_place_id": f"place-{name}" if verified else None,
    }


@pytest.mark.anyio
async def test_calculates_total_driving_route(monkeypatch):
    calls = []

    async def fake_get_driving_route(*coordinates):
        calls.append(coordinates)
        return DrivingRoute(
            distance_km=12.5,
            duration_minutes=20,
        )

    monkeypatch.setattr(
        itinerary_routes,
        "get_driving_route",
        fake_get_driving_route,
    )

    trip = make_trip([
        make_activity("A", 18.7, 98.9),
        make_activity("B", 18.8, 98.9),
        make_activity("C", 18.9, 98.9),
    ])

    result = await itinerary_routes.add_driving_routes(trip)

    assert len(calls) == 2
    assert result.days[0].driving_distance_km == 25.0
    assert result.days[0].driving_duration_minutes == 40


@pytest.mark.anyio
async def test_skips_day_with_one_activity(monkeypatch):
    async def unexpected_route(*coordinates):
        raise AssertionError("Google Routes should not be called.")

    monkeypatch.setattr(
        itinerary_routes,
        "get_driving_route",
        unexpected_route,
    )

    trip = make_trip([
        make_activity("A", 18.7, 98.9),
    ])

    result = await itinerary_routes.add_driving_routes(trip)

    assert result.days[0].driving_distance_km is None
    assert result.days[0].driving_duration_minutes is None


@pytest.mark.anyio
async def test_does_not_calculate_unverified_route(monkeypatch):
    async def unexpected_route(*coordinates):
        raise AssertionError("Google Routes should not be called.")

    monkeypatch.setattr(
        itinerary_routes,
        "get_driving_route",
        unexpected_route,
    )

    trip = make_trip([
        make_activity("A", 18.7, 98.9),
        make_activity("B", 18.8, 98.9, verified=False),
    ])

    result = await itinerary_routes.add_driving_routes(trip)

    assert result.days[0].driving_distance_km is None
    assert result.days[0].driving_duration_minutes is None


@pytest.mark.anyio
async def test_keeps_trip_when_routes_api_fails(monkeypatch):
    async def failing_route(*coordinates):
        raise httpx.ConnectError("Google Routes unavailable")

    monkeypatch.setattr(
        itinerary_routes,
        "get_driving_route",
        failing_route,
    )

    trip = make_trip([
        make_activity("A", 18.7, 98.9),
        make_activity("B", 18.8, 98.9),
    ])

    result = await itinerary_routes.add_driving_routes(trip)

    assert len(result.days[0].activities) == 2
    assert result.days[0].driving_distance_km is None
    assert result.days[0].driving_duration_minutes is None