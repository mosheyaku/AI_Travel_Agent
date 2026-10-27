
import json

import pytest

from app import trip_generator
from app.schemas import TravelPreferences


@pytest.mark.anyio
async def test_generate_trip_plan(monkeypatch):
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["adventure", "nature"],
        pace="active",
    )

    recommendations = [
        {
            "name": "Skyline Adventure",
            "description": "Ziplining through the jungle.",
            "source_indices": [1],
        },
        {
            "name": "Doi Inthanon National Park",
            "description": "Hiking and scenic viewpoints.",
            "source_indices": [2],
        },
    ]

    async def fake_generate_text(prompt: str) -> str:
        return json.dumps(
            {
                "destination": "Chiang Mai, Thailand",
                "days": [
                    {
                        "day": 1,
                        "activities": [
                            {
                                "name": "Skyline Adventure",
                                "description": "Ziplining through the jungle.",
                                "source_indices": [1],
                            }
                        ],
                    },
                    {
                        "day": 2,
                        "activities": [
                            {
                                "name": "Doi Inthanon National Park",
                                "description": "Hiking and scenic viewpoints.",
                                "source_indices": [2],
                            }
                        ],
                    },
                ],
            }
        )

    monkeypatch.setattr(trip_generator, "generate_text", fake_generate_text)

    result = await trip_generator.generate_trip_plan(
        preferences,
        recommendations,
    )

    assert len(result.days) == 2
    assert result.days[0].activities[0].name == "Skyline Adventure"
    assert result.days[1].activities[0].name == "Doi Inthanon National Park"


@pytest.mark.anyio
async def test_rejects_incorrect_number_of_days(monkeypatch):
    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": []
                }
            ]
        })

    monkeypatch.setattr(trip_generator, "generate_text", fake_generate_text)

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["adventure"],
    )

    with pytest.raises(
        ValueError,
        match="does not match the requested number of days",
    ):
        await trip_generator.generate_trip_plan(preferences, [])


@pytest.mark.anyio
async def test_rejects_unknown_attraction(monkeypatch):
    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Invented Adventure Park",
                            "description": "An invented attraction.",
                            "source_indices": [1],
                        }
                    ],
                }
            ],
        })

    monkeypatch.setattr(trip_generator, "generate_text", fake_generate_text)

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["adventure"],
    )

    recommendations = [
        {
            "name": "Skyline Adventure",
            "category": "adventure",
            "description": "Ziplining in Chiang Mai.",
            "relevance_reason": "Matches adventure interests.",
            "source_indices": [1],
        }
    ]

    with pytest.raises(ValueError, match="unknown attraction"):
        await trip_generator.generate_trip_plan(preferences, recommendations)


@pytest.mark.anyio
async def test_rejects_duplicate_attraction(monkeypatch):
    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Skyline Adventure",
                            "description": "Ziplining in the jungle.",
                            "source_indices": [1],
                        }
                    ],
                },
                {
                    "day": 2,
                    "activities": [
                        {
                            "name": "Skyline Adventure",
                            "description": "Another visit to the same attraction.",
                            "source_indices": [1],
                        }
                    ],
                },
            ],
        })

    monkeypatch.setattr(trip_generator, "generate_text", fake_generate_text)

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["adventure"],
    )

    recommendations = [
        {
            "name": "Skyline Adventure",
            "category": "adventure",
            "description": "Ziplining in Chiang Mai.",
            "relevance_reason": "Matches adventure interests.",
            "source_indices": [1],
        }
    ]

    with pytest.raises(ValueError, match="duplicate attraction"):
        await trip_generator.generate_trip_plan(preferences, recommendations)


@pytest.mark.anyio
async def test_rejects_modified_source_indices(monkeypatch):
    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Skyline Adventure",
                            "description": "Ziplining in Chiang Mai.",
                            "source_indices": [99],
                        }
                    ],
                }
            ],
        })

    monkeypatch.setattr(trip_generator, "generate_text", fake_generate_text)

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["adventure"],
    )

    recommendations = [
        {
            "name": "Skyline Adventure",
            "category": "adventure",
            "description": "Ziplining in Chiang Mai.",
            "relevance_reason": "Matches adventure interests.",
            "source_indices": [1],
        }
    ]

    with pytest.raises(ValueError, match="incorrect sources"):
        await trip_generator.generate_trip_plan(preferences, recommendations)


@pytest.mark.anyio
async def test_preserves_verified_attraction_location(monkeypatch):
    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Elephant Nature Park",
                            "description": "Visit an elephant sanctuary.",
                            "source_indices": [1],
                            "google_place_id": "fake-place-id",
                            "latitude": 0.0,
                            "longitude": 0.0,
                        }
                    ],
                }
            ],
        })

    monkeypatch.setattr(trip_generator, "generate_text", fake_generate_text)

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["wildlife"],
    )

    recommendations = [
        {
            "name": "Elephant Nature Park",
            "category": "wildlife",
            "description": "Visit an elephant sanctuary in Chiang Mai.",
            "relevance_reason": "Matches wildlife interests.",
            "source_indices": [1],
            "location_status": "verified",
            "latitude": 19.2171729,
            "longitude": 98.860038,
            "google_place_id": "real-place-id",
        }
    ]

    trip = await trip_generator.generate_trip_plan(
        preferences,
        recommendations,
    )

    activity = trip.days[0].activities[0]

    assert activity.name == "Elephant Nature Park"
    assert activity.google_place_id == "real-place-id"
    assert activity.latitude == 19.2171729
    assert activity.longitude == 98.860038
    assert activity.location_status == "verified"


@pytest.mark.anyio
async def test_calculates_itinerary_day_distance(monkeypatch):
    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Attraction A",
                            "description": "First attraction.",
                            "source_indices": [1],
                        },
                        {
                            "name": "Attraction B",
                            "description": "Second attraction.",
                            "source_indices": [2],
                        },
                    ],
                }
            ],
        })

    monkeypatch.setattr(trip_generator, "generate_text", fake_generate_text)

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["nature"],
    )

    recommendations = [
        {
            "name": "Attraction A",
            "source_indices": [1],
            "latitude": 18.7883,
            "longitude": 98.9853,
        },
        {
            "name": "Attraction B",
            "source_indices": [2],
            "latitude": 19.2000,
            "longitude": 98.8600,
        },
    ]

    trip = await trip_generator.generate_trip_plan(
        preferences,
        recommendations,
    )

    assert trip.days[0].max_distance_km is not None
    assert trip.days[0].max_distance_km > 40


@pytest.mark.anyio
async def test_includes_attraction_distances_in_prompt(monkeypatch):
    captured_prompts = []

    async def fake_generate_text(prompt: str) -> str:
        captured_prompts.append(prompt)

        return json.dumps({
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Attraction A",
                            "description": "First attraction.",
                            "source_indices": [1],
                        },
                        {
                            "name": "Attraction B",
                            "description": "Second attraction.",
                            "source_indices": [2],
                        },
                    ],
                }
            ],
        })

    monkeypatch.setattr(trip_generator, "generate_text", fake_generate_text)

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["nature"],
    )

    recommendations = [
        {
            "name": "Attraction A",
            "source_indices": [1],
            "latitude": 18.7883,
            "longitude": 98.9853,
            "google_place_id": "place-a",
        },
        {
            "name": "Attraction B",
            "source_indices": [2],
            "latitude": 19.2000,
            "longitude": 98.8600,
            "google_place_id": "place-b",
        },
    ]

    await trip_generator.generate_trip_plan(
        preferences,
        recommendations,
    )

    prompt = captured_prompts[0]

    assert "Straight-line distances between verified attractions" in prompt
    assert '"from": "Attraction A"' in prompt
    assert '"to": "Attraction B"' in prompt
    assert '"distance_km":' in prompt