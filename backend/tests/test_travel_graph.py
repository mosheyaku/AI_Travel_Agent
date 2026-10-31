from unittest.mock import AsyncMock

import pytest

from app import travel_graph
from app.location_validation import LocationStatus
from app.schemas import TravelItinerary, TravelPreferences


@pytest.fixture
def preferences():
    return TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=1,
        interests=["nature"],
    )


@pytest.fixture
def recommendations():
    return [
        {
            "name": "Test Park",
            "activity_type": "hiking",
            "description": "A nature park.",
            "source_indices": [1],
            "location_status": LocationStatus.VERIFIED,
            "latitude": 18.7,
            "longitude": 98.9,
            "google_place_id": "test-place",
        }
    ]


def make_trip():
    return TravelItinerary.model_validate(
        {
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Test Park",
                            "activity_type": "hiking",
                            "description": "A nature park.",
                            "source_indices": [1],
                        }
                    ],
                }
            ],
        }
    )


@pytest.fixture
def mock_recommendations(monkeypatch, recommendations):
    mock = AsyncMock(
        return_value={
            "recommendations": recommendations,
            "sources": [{"title": "Test Source", "url": "https://example.com"}],
        }
    )

    monkeypatch.setattr(
        travel_graph,
        "recommend_attractions",
        mock,
    )

    return mock


@pytest.mark.anyio
async def test_graph_generates_valid_trip(
    monkeypatch,
    preferences,
    mock_recommendations,
):
    mock_generate = AsyncMock(return_value=make_trip())
    mock_evaluate = AsyncMock(return_value=[])

    monkeypatch.setattr(
        travel_graph,
        "generate_trip_candidate",
        mock_generate,
    )
    monkeypatch.setattr(
        travel_graph,
        "evaluate_trip_candidate",
        mock_evaluate,
    )

    result = await travel_graph.travel_graph.ainvoke(
        {
            "preferences": preferences,
        }
    )

    assert result["trip"]["destination"] == "Chiang Mai, Thailand"
    assert len(result["sources"]) == 1

    mock_generate.assert_awaited_once()
    mock_evaluate.assert_awaited_once()


@pytest.mark.anyio
async def test_graph_retries_invalid_candidate(
    monkeypatch,
    preferences,
    mock_recommendations,
):
    mock_generate = AsyncMock(
        side_effect=[
            ValueError("Invalid JSON"),
            make_trip(),
        ]
    )
    mock_evaluate = AsyncMock(return_value=[])

    monkeypatch.setattr(
        travel_graph,
        "generate_trip_candidate",
        mock_generate,
    )
    monkeypatch.setattr(
        travel_graph,
        "evaluate_trip_candidate",
        mock_evaluate,
    )

    result = await travel_graph.travel_graph.ainvoke(
        {
            "preferences": preferences,
        }
    )

    assert result["attempts"] == 2
    assert mock_generate.await_count == 2
    assert "Invalid JSON" in mock_generate.await_args_list[1].args[0]
    assert result["trip"]["days"][0]["activities"][0]["name"] == "Test Park"


@pytest.mark.anyio
async def test_graph_repairs_invalid_trip(
    monkeypatch,
    preferences,
    mock_recommendations,
):
    mock_generate = AsyncMock(return_value=make_trip())
    mock_evaluate = AsyncMock(return_value=["Day 1: invalid route"])
    mock_repair = AsyncMock(return_value=make_trip())

    monkeypatch.setattr(
        travel_graph,
        "generate_trip_candidate",
        mock_generate,
    )
    monkeypatch.setattr(
        travel_graph,
        "evaluate_trip_candidate",
        mock_evaluate,
    )
    monkeypatch.setattr(
        travel_graph,
        "repair_trip_plan",
        mock_repair,
    )
    monkeypatch.setattr(
        travel_graph,
        "resolve_trip_origin",
        AsyncMock(return_value=None),
    )

    result = await travel_graph.travel_graph.ainvoke(
        {
            "preferences": preferences,
        }
    )

    assert result["attempts"] == 2
    mock_repair.assert_awaited_once()
    assert result["trip"]["destination"] == "Chiang Mai, Thailand"


@pytest.mark.anyio
async def test_graph_rejects_unverified_attractions(
    monkeypatch,
    preferences,
    recommendations,
):
    recommendations[0]["location_status"] = LocationStatus.UNVERIFIED

    monkeypatch.setattr(
        travel_graph,
        "recommend_attractions",
        AsyncMock(
            return_value={
                "recommendations": recommendations,
                "sources": [],
            }
        ),
    )

    with pytest.raises(
        ValueError,
        match="No attractions with verified locations",
    ):
        await travel_graph.travel_graph.ainvoke(
            {
                "preferences": preferences,
            }
        )


@pytest.mark.anyio
async def test_graph_selects_best_driving_fallback(
    monkeypatch,
    preferences,
    mock_recommendations,
):
    first_trip = make_trip()
    first_trip.days[0].total_driving_duration_minutes = 250

    second_trip = make_trip()
    second_trip.days[0].total_driving_duration_minutes = 200

    mock_generate = AsyncMock(side_effect=[first_trip, second_trip])

    mock_evaluate = AsyncMock(return_value=["Day 1: excessive total driving time"])

    monkeypatch.setattr(
        travel_graph,
        "generate_trip_candidate",
        mock_generate,
    )
    monkeypatch.setattr(
        travel_graph,
        "evaluate_trip_candidate",
        mock_evaluate,
    )
    monkeypatch.setattr(
        travel_graph,
        "find_planning_issues",
        lambda trip, pace: [],
    )
    monkeypatch.setattr(
        travel_graph,
        "find_driving_issues",
        lambda trip: [],
    )
    monkeypatch.setattr(
        travel_graph,
        "find_total_driving_issues",
        lambda trip: ["Excessive total driving"],
    )

    result = await travel_graph.travel_graph.ainvoke(
        {
            "preferences": preferences,
        }
    )

    assert result["attempts"] == 2
    assert mock_generate.await_count == 2
    assert result["trip"]["days"][0]["total_driving_duration_minutes"] == 200
