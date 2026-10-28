
import json

import pytest

from app import trip_generator
from app.location_validation import LocationStatus
from app.schemas import TravelItinerary, TravelPreferences
from app.trip_generator import find_activity_load_issues


def verified_attraction(name, source_index, **extra):
    data = {
        "name": name,
        "source_indices": [source_index],
        "location_status": LocationStatus.VERIFIED,
        "latitude": 18.7,
        "longitude": 98.9,
        "google_place_id": f"test-place-{source_index}",
    }
    data.update(extra)
    return data


@pytest.fixture
def mock_driving_routes(monkeypatch):
    async def fake_add_driving_routes(trip):
        return trip

    monkeypatch.setattr(
        trip_generator,
        "add_driving_routes",
        fake_add_driving_routes,
    )


@pytest.mark.anyio
async def test_generate_trip_plan(monkeypatch):
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["adventure", "nature"],
        pace="active",
    )

    recommendations = [
        verified_attraction(
            "Skyline Adventure",
            1,
            description="Ziplining through the jungle.",
        ),
        verified_attraction(
            "Doi Inthanon National Park",
            2,
            description="Hiking and scenic viewpoints.",
        ),
    ]

    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
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
        })

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

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
                    "activities": [],
                }
            ],
        })

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["adventure"],
    )

    recommendations = [
        verified_attraction("Test Park", 1),
    ]

    with pytest.raises(
        ValueError,
        match="does not match the requested number of days",
    ):
        await trip_generator.generate_trip_plan(
            preferences,
            recommendations,
        )


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

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["adventure"],
    )

    recommendations = [
        verified_attraction(
            "Skyline Adventure",
            1,
            category="adventure",
            description="Ziplining in Chiang Mai.",
            relevance_reason="Matches adventure interests.",
        ),
    ]

    with pytest.raises(ValueError, match="unknown attraction"):
        await trip_generator.generate_trip_plan(
            preferences,
            recommendations,
        )


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

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["adventure"],
    )

    recommendations = [
        verified_attraction(
            "Skyline Adventure",
            1,
            category="adventure",
            description="Ziplining in Chiang Mai.",
            relevance_reason="Matches adventure interests.",
        ),
    ]

    with pytest.raises(ValueError, match="duplicate attraction"):
        await trip_generator.generate_trip_plan(
            preferences,
            recommendations,
        )


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

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["adventure"],
    )

    recommendations = [
        verified_attraction(
            "Skyline Adventure",
            1,
            category="adventure",
            description="Ziplining in Chiang Mai.",
            relevance_reason="Matches adventure interests.",
        ),
    ]

    with pytest.raises(ValueError, match="incorrect sources"):
        await trip_generator.generate_trip_plan(
            preferences,
            recommendations,
        )


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

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["wildlife"],
    )

    recommendations = [
        verified_attraction(
            "Elephant Nature Park",
            1,
            category="wildlife",
            description="Visit an elephant sanctuary in Chiang Mai.",
            relevance_reason="Matches wildlife interests.",
            latitude=19.2171729,
            longitude=98.860038,
            google_place_id="real-place-id",
        ),
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
    assert activity.location_status == LocationStatus.VERIFIED


@pytest.mark.anyio
async def test_calculates_itinerary_day_distance(
    monkeypatch,
    mock_driving_routes,
):
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

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["nature"],
    )

    recommendations = [
        verified_attraction(
            "Attraction A",
            1,
            latitude=18.7883,
            longitude=98.9853,
        ),
        verified_attraction(
            "Attraction B",
            2,
            latitude=18.7900,
            longitude=98.9900,
        ),
    ]

    trip = await trip_generator.generate_trip_plan(
        preferences,
        recommendations,
    )

    assert trip.days[0].max_distance_km is not None
    assert trip.days[0].max_distance_km == 0.5


@pytest.mark.anyio
async def test_includes_attraction_distances_in_prompt(
    monkeypatch,
    mock_driving_routes,
):
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

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["nature"],
    )

    recommendations = [
        verified_attraction(
            "Attraction A",
            1,
            latitude=18.7883,
            longitude=98.9853,
            google_place_id="place-a",
        ),
        verified_attraction(
            "Attraction B",
            2,
            latitude=18.7900,
            longitude=98.9900,
            google_place_id="place-b",
        ),
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


def test_rejects_full_day_activity_with_another_activity():
    trip = TravelItinerary.model_validate({
        "destination": "Chiang Mai",
        "days": [{
            "day": 1,
            "activities": [
                {
                    "name": "Full-day tour",
                    "description": "A full-day tour.",
                    "source_indices": [1],
                    "duration_type": "full_day",
                },
                {
                    "name": "Waterfall",
                    "description": "A waterfall visit.",
                    "source_indices": [2],
                    "duration_type": "short",
                },
            ],
        }],
    })

    issues = find_activity_load_issues(trip)

    assert len(issues) == 1
    assert "full-day" in issues[0]


@pytest.mark.anyio
async def test_excludes_unverified_attractions(monkeypatch):
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["adventure"],
        pace="balanced",
    )

    recommendations = [
        verified_attraction(
            "Verified Park",
            1,
            description="Adventure park",
            google_place_id="verified-place",
        ),
        {
            "name": "Unknown Park",
            "description": "Adventure park",
            "source_indices": [2],
            "location_status": LocationStatus.UNVERIFIED,
            "latitude": None,
            "longitude": None,
            "google_place_id": None,
        },
    ]

    async def fake_generate_text(prompt: str) -> str:
        assert "Verified Park" in prompt
        assert "Unknown Park" not in prompt

        return json.dumps({
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Verified Park",
                            "description": "Adventure park",
                            "source_indices": [1],
                        }
                    ],
                }
            ],
        })

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    result = await trip_generator.generate_trip_plan(
        preferences,
        recommendations,
    )

    assert len(result.days[0].activities) == 1
    assert result.days[0].activities[0].name == "Verified Park"
    assert (
        result.days[0].activities[0].location_status
        == LocationStatus.VERIFIED
    )


@pytest.mark.anyio
async def test_rejects_trip_without_verified_attractions(monkeypatch):
    async def fake_generate_text(prompt: str) -> str:
        pytest.fail("LLM should not be called without verified attractions")

    monkeypatch.setattr(
        trip_generator,
        "generate_text",
        fake_generate_text,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["adventure"],
    )

    recommendations = [
        {
            "name": "Unknown Park",
            "source_indices": [1],
            "location_status": LocationStatus.UNVERIFIED,
            "latitude": None,
            "longitude": None,
            "google_place_id": None,
        },
    ]

    with pytest.raises(
        ValueError,
        match="No attractions with verified locations",
    ):
        await trip_generator.generate_trip_plan(
            preferences,
            recommendations,
        )