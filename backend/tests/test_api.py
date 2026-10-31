from fastapi.testclient import TestClient

from app.main import app
from app import main


client = TestClient(app)


def test_recommendation_error_returns_502(monkeypatch):
    async def fail_recommendations(query: str) -> dict:
        raise ValueError("Internal model details")

    monkeypatch.setattr(
        main,
        "recommend_attractions",
        fail_recommendations,
    )

    response = client.get(
        "/attractions/recommend",
        params={"query": "temples in Kyoto"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The recommendation service returned an invalid response."
    }


def test_accepts_valid_travel_preferences():
    response = client.post(
        "/trips/preferences",
        json={
            "destination": "Thailand",
            "duration_days": 14,
            "interests": ["adventure", "nature"],
            "pace": "active",
        },
    )

    assert response.status_code == 200
    assert response.json()["destination"] == "Thailand"
    assert response.json()["pace"] == "active"


def test_rejects_invalid_travel_preferences():
    response = client.post(
        "/trips/preferences",
        json={
            "destination": "Thailand",
            "duration_days": 0,
            "interests": ["adventure"],
        },
    )

    assert response.status_code == 422


from unittest.mock import AsyncMock

from app import main


def test_accommodation_suggestions(monkeypatch):
    mock_search = AsyncMock(
        return_value=[
            {
                "place_id": "hotel-123",
                "name": "Example Hotel",
                "address": "Chiang Mai, Thailand",
                "latitude": 18.79,
                "longitude": 98.98,
            }
        ]
    )

    monkeypatch.setattr(
        main,
        "search_accommodations",
        mock_search,
    )

    client = TestClient(main.app)

    response = client.get(
        "/places/accommodations",
        params={
            "query": "Example Hotel",
            "destination": "Chiang Mai",
        },
    )

    assert response.status_code == 200

    assert response.json() == [
        {
            "place_id": "hotel-123",
            "name": "Example Hotel",
            "address": "Chiang Mai, Thailand",
            "latitude": 18.79,
            "longitude": 98.98,
        }
    ]

    mock_search.assert_awaited_once_with(
        "Example Hotel",
        "Chiang Mai",
    )
