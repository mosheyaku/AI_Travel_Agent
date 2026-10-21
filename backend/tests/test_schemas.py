
import pytest
from pydantic import ValidationError

from app.schemas import AttractionRecommendations


def make_recommendation(name: str, category: str = "culture") -> dict:
    return {
        "name": name,
        "category": category,
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


def test_rejects_more_than_five_recommendations():
    data = {
        "recommendations": [
            make_recommendation(f"Attraction {index}")
            for index in range(6)
        ]
    }

    with pytest.raises(ValidationError):
        AttractionRecommendations.model_validate(data)
