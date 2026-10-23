
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
