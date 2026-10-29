import pytest

from app import trip_generator
from app.location_validation import LocationStatus
from app.schemas import TravelItinerary, TravelPreferences


def make_activity(name, index, duration_type="unknown"):
    return {
        "name": name,
        "activity_type": "other",
        "description": name,
        "source_indices": [index],
        "location_status": LocationStatus.VERIFIED,
        "latitude": 18.7,
        "longitude": 98.9,
        "google_place_id": f"place-{index}",
        "duration_type": duration_type,
    }


def make_preferences(days):
    return TravelPreferences(
        destination="Chiang Mai",
        duration_days=days,
        interests=["nature"],
    )


async def fake_valid_routes(trip):
    for day in trip.days:
        day.driving_duration_minutes = (
            10 if len(day.activities) > 1 else None
        )
        day.driving_status = "verified"

    return trip


@pytest.mark.anyio
async def test_repair_moves_activity_without_dropping_it(monkeypatch):
    recommendations = [
        make_activity("A", 1),
        make_activity("B", 2),
        make_activity("C", 3),
    ]

    trip = TravelItinerary.model_validate({
        "destination": "Chiang Mai",
        "days": [
            {"day": 1, "activities": recommendations[:2]},
            {"day": 2, "activities": recommendations[2:]},
        ],
    })

    async def fake_routes(candidate):
        for day in candidate.days:
            names = [activity.name for activity in day.activities]

            minutes = (
                139
                if names in (["A", "B"], ["B", "A"])
                else 10
            )

            day.driving_duration_minutes = (
                minutes if len(names) > 1 else None
            )
            day.driving_status = (
                "exceeds_limit"
                if minutes > 90
                else "verified"
            )

        return candidate

    monkeypatch.setattr(
        trip_generator,
        "add_driving_routes",
        fake_routes,
    )

    await fake_routes(trip)

    repaired = await trip_generator.repair_trip_plan(
        trip,
        make_preferences(2),
        recommendations,
    )

    assert repaired is not None
    assert len(repaired.days) == 2

    assert sorted(
        activity.name
        for day in repaired.days
        for activity in day.activities
    ) == ["A", "B", "C"]

    assert not trip_generator.find_driving_issues(repaired)


@pytest.mark.anyio
async def test_repair_separates_full_day_activity(monkeypatch):
    recommendations = [
        make_activity("National Park", 1, "full_day"),
        make_activity("Botanical Garden", 2, "short"),
    ]

    trip = TravelItinerary.model_validate({
        "destination": "Chiang Mai",
        "days": [
            {"day": 1, "activities": recommendations},
            {"day": 2, "activities": []},
        ],
    })

    monkeypatch.setattr(
        trip_generator,
        "add_driving_routes",
        fake_valid_routes,
    )

    repaired = await trip_generator.repair_trip_plan(
        trip,
        make_preferences(2),
        recommendations,
    )

    assert repaired is not None
    assert len(repaired.days) == 2
    assert not trip_generator.find_activity_load_issues(repaired)

    assert sorted(
        activity.name
        for day in repaired.days
        for activity in day.activities
    ) == ["Botanical Garden", "National Park"]

    assert all(len(day.activities) == 1 for day in repaired.days)


@pytest.mark.anyio
async def test_repair_does_not_accept_unknown_routes(monkeypatch):
    recommendations = [
        make_activity("A", 1),
        make_activity("B", 2),
    ]

    trip = TravelItinerary.model_validate({
        "destination": "Chiang Mai",
        "days": [
            {"day": 1, "activities": recommendations},
        ],
    })

    async def unknown_routes(candidate):
        for day in candidate.days:
            day.driving_status = "unknown"

        return candidate

    monkeypatch.setattr(
        trip_generator,
        "add_driving_routes",
        unknown_routes,
    )

    repaired = await trip_generator.repair_trip_plan(
        trip,
        make_preferences(1),
        recommendations,
    )

    assert repaired is not None
    assert len(repaired.days[0].activities) == 1