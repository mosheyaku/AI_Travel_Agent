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
