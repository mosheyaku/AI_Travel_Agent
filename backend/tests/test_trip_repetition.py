import json

import pytest

from app import trip_generator
from app.location_validation import LocationStatus
from app.schemas import TravelPreferences

from app.schemas import TravelItinerary
from app.trip_generator import find_repetitive_experience_issues


def make_activity(name: str, activity_type: str, source_index: int) -> dict:
    return {
        "name": name,
        "activity_type": activity_type,
        "description": "Test activity.",
        "source_indices": [source_index],
    }


def make_trip(days: list[list[dict]]) -> TravelItinerary:
    return TravelItinerary.model_validate({
        "destination": "Chiang Mai, Thailand",
        "days": [
            {
                "day": index,
                "activities": activities,
            }
            for index, activities in enumerate(days, start=1)
        ],
    })


def test_detects_repeated_elephant_sanctuaries():
    trip = make_trip([
        [make_activity("Elephant Nature Park", "elephant_sanctuary", 1)],
        [make_activity("Elephant Jungle Sanctuary", "elephant_sanctuary", 2)],
    ])

    issues = find_repetitive_experience_issues(trip)

    assert len(issues) == 1
    assert "Elephant Jungle Sanctuary" in issues[0]
    assert "Elephant Nature Park" in issues[0]


def test_allows_different_hiking_experiences():
    trip = make_trip([
        [make_activity("Doi Inthanon", "hiking", 1)],
        [make_activity("Doi Suthep Trail", "hiking", 2)],
    ])

    issues = find_repetitive_experience_issues(trip)

    assert issues == []


def test_detects_repeated_zipline_experiences():
    trip = make_trip([
        [make_activity("Skyline Adventure", "zipline", 1)],
        [make_activity("Jungle Flight", "zipline", 2)],
    ])

    issues = find_repetitive_experience_issues(trip)

    assert len(issues) == 1
    assert "zipline" in issues[0]


def test_allows_different_activity_types():
    trip = make_trip([
        [make_activity("Skyline Adventure", "zipline", 1)],
        [make_activity("Elephant Nature Park", "elephant_sanctuary", 2)],
        [make_activity("Mae Taeng River", "rafting", 3)],
    ])

    issues = find_repetitive_experience_issues(trip)

    assert issues == []


@pytest.mark.anyio
async def test_retries_when_experiences_repeat(monkeypatch):
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["wildlife", "adventure"],
        pace="balanced",
    )

    recommendations = [
        {
            "name": "Elephant Nature Park",
            "activity_type": "elephant_sanctuary",
            "description": "Visit an elephant sanctuary.",
            "source_indices": [1],
            "location_status": LocationStatus.VERIFIED,
            "latitude": 18.8,
            "longitude": 98.9,
            "google_place_id": "elephant-1",
        },
        {
            "name": "Elephant Jungle Sanctuary",
            "activity_type": "elephant_sanctuary",
            "description": "Visit another elephant sanctuary.",
            "source_indices": [2],
            "location_status": LocationStatus.VERIFIED,
            "latitude": 18.9,
            "longitude": 98.9,
            "google_place_id": "elephant-2",
        },
        {
            "name": "Mae Taeng Rafting",
            "activity_type": "rafting",
            "description": "White-water rafting.",
            "source_indices": [3],
            "location_status": LocationStatus.VERIFIED,
            "latitude": 18.85,
            "longitude": 98.9,
            "google_place_id": "rafting-1",
        },
    ]

    generated_plans = [
        [
            ("Elephant Nature Park", "elephant_sanctuary", 1),
            ("Elephant Jungle Sanctuary", "elephant_sanctuary", 2),
        ],
        [
            ("Elephant Nature Park", "elephant_sanctuary", 1),
            ("Mae Taeng Rafting", "rafting", 3),
        ],
    ]

    prompts = []

    async def fake_generate_text(prompt):
        prompts.append(prompt)
        plan = generated_plans[len(prompts) - 1]

        return json.dumps({
            "destination": preferences.destination,
            "days": [
                {
                    "day": day_number,
                    "activities": [
                        {
                            "name": name,
                            "activity_type": activity_type,
                            "description": "Test activity.",
                            "source_indices": [source_index],
                        }
                    ],
                }
                for day_number, (name, activity_type, source_index)
                in enumerate(plan, start=1)
            ],
        })

    async def fake_add_driving_routes(trip):
        return trip

    async def fake_find_trip_origin(destination):
        return None

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
    monkeypatch.setattr(
        trip_generator,
        "find_trip_origin",
        fake_find_trip_origin,
    )

    trip = await trip_generator.generate_trip_plan(
        preferences,
        recommendations,
    )

    assert len(prompts) == 2
    assert "elephant_sanctuary" in prompts[1]
    assert trip.days[0].activities[0].name == "Elephant Nature Park"
    assert trip.days[1].activities[0].name == "Mae Taeng Rafting"
