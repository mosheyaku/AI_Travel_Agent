import pytest
from pydantic import ValidationError

from app.schemas import AttractionRecommendations, TravelPreferences, TravelItinerary


def make_recommendation(name: str, category: str = "culture") -> dict:
    return {
        "name": name,
        "category": category,
        "activity_type": "temple",
        "description": "A historical attraction.",
        "relevance_reason": "Matches the user's request.",
        "source_indices": [1],
    }


def test_accepts_valid_recommendation():
    data = {
        "recommendations": [
            make_recommendation("Kiyomizudera Temple")
        ]
    }

    result = AttractionRecommendations.model_validate(data)

    assert len(result.recommendations) == 1
    assert result.recommendations[0].category == "culture"


def test_rejects_invalid_category():
    data = {
        "recommendations": [
            make_recommendation("Kiyomizudera Temple", "temples")
        ]
    }

    with pytest.raises(ValidationError):
        AttractionRecommendations.model_validate(data)


def test_rejects_duplicate_names():
    data = {
        "recommendations": [
            make_recommendation("Kiyomizudera Temple"),
            make_recommendation("kiyomizudera temple"),
        ]
    }

    with pytest.raises(ValidationError):
        AttractionRecommendations.model_validate(data)


def test_rejects_more_than_fifteen_recommendations():
    data = {
        "recommendations": [
            make_recommendation(f"Attraction {index}")
            for index in range(16)
        ]
    }

    with pytest.raises(ValidationError):
        AttractionRecommendations.model_validate(data)


def test_accepts_valid_travel_preferences():
    preferences = TravelPreferences(
        destination="Thailand",
        duration_days=14,
        interests=["adventure", "nature"],
        pace="active",
    )

    assert preferences.destination == "Thailand"
    assert preferences.duration_days == 14
    assert preferences.budget is None


def test_rejects_invalid_trip_duration():
    with pytest.raises(ValidationError):
        TravelPreferences(
            destination="Thailand",
            duration_days=0,
            interests=["adventure"],
        )


def test_rejects_invalid_interest():
    with pytest.raises(ValidationError):
        TravelPreferences(
            destination="Thailand",
            duration_days=14,
            interests=["shopping"],
        )


def test_accepts_valid_itinerary():
    itinerary = TravelItinerary.model_validate(
        {
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Skyline Adventure",
                            "activity_type": "zipline",
                            "description": "Ziplining through the jungle.",
                            "source_indices": [1],
                        }
                    ],
                }
            ],
        }
    )

    assert itinerary.destination == "Chiang Mai, Thailand"
    assert itinerary.days[0].day == 1
    assert itinerary.days[0].activities[0].name == "Skyline Adventure"
    assert itinerary.days[0].activities[0].activity_type == "zipline"