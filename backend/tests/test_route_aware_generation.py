import json

import pytest

from app import trip_generator
from app.schemas import TravelPreferences
from app.location_validation import LocationStatus


@pytest.mark.anyio
async def test_retries_when_driving_time_is_too_long(monkeypatch):
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["nature"],
        pace="balanced",
    )

    recommendations = [
        {
            "name": name,
            "activity_type": "other",
            "description": "Nature attraction",
            "source_indices": [index],
            "location_status": LocationStatus.VERIFIED,
            "latitude": 18.7 + index * 0.001,
            "longitude": 98.9,
            "google_place_id": f"test-place-{index}",
        }
        for index, name in enumerate(["A", "B"], start=1)
    ]

    prompts = []

    async def fake_generate_text(prompt):
        prompts.append(prompt)
        return json.dumps({
            "destination": preferences.destination,
            "days": [{
                "day": 1,
                "activities": [
                    {
                        "name": "A",
                        "activity_type": "other",
                        "description": "Nature attraction",
                        "source_indices": [1],
                    },
                    {
                        "name": "B",
                        "activity_type": "other",
                        "description": "Nature attraction",
                        "source_indices": [2],
                    },
                ],
            }],
        })

    route_calls = 0

    async def fake_add_driving_routes(trip):
        nonlocal route_calls
        route_calls += 1

        trip.days[0].driving_duration_minutes = (
            120 if route_calls == 1 else 40
        )
        return trip

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )
    monkeypatch.setattr(
        trip_generator,
        "add_driving_routes",
        fake_add_driving_routes,
    )

    result = await trip_generator.generate_trip_plan(
        preferences,
        recommendations,
    )

    assert len(prompts) == 2
    assert "120 minutes" in prompts[1]
    assert result.days[0].driving_duration_minutes == 40