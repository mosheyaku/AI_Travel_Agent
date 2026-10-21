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
