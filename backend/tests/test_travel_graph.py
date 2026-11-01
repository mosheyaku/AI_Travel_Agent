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
            "sources": [
                {
                    "title": "Test Source",
                    "url": "https://example.com",
                }
            ],
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


@pytest.mark.anyio
async def test_graph_schedule_returns_repaired_activity_order(monkeypatch):
    trip = TravelItinerary.model_validate(
        {
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Activity 1",
                            "activity_type": "hiking",
                            "description": "First activity",
                            "source_indices": [1],
                            "duration_type": "short",
                        },
                        {
                            "name": "Activity 2",
                            "activity_type": "hiking",
                            "description": "Second activity",
                            "source_indices": [1],
                            "duration_type": "short",
                        },
                    ],
                }
            ],
        }
    )

    async def mock_schedule(
        candidate,
        start_time="09:00",
        origin=None,
    ):
        return candidate

    async def mock_validation(candidate):
        activities = candidate.days[0].activities

        for activity in activities:
            activity.opening_hours_status = "verified"

        if activities[0].name == "Activity 1":
            activities[1].opening_hours_status = "conflict"

        return candidate

    async def mock_repair(candidate, origin=None):
        candidate.days[0].activities.reverse()
        await mock_validation(candidate)
        return candidate

    mock_repair_fn = AsyncMock(side_effect=mock_repair)

    monkeypatch.setattr(
        travel_graph,
        "resolve_trip_origin",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        travel_graph,
        "add_itinerary_schedule",
        mock_schedule,
    )
    monkeypatch.setattr(
        travel_graph,
        "validate_itinerary_opening_hours",
        mock_validation,
    )
    monkeypatch.setattr(
        travel_graph,
        "repair_opening_hours_conflicts",
        mock_repair_fn,
    )

    result = await travel_graph.schedule_node(
        {
            "trip": trip.model_dump(),
            "preferences": TravelPreferences(
                destination="Chiang Mai, Thailand",
                duration_days=1,
                interests=["nature"],
            ),
        }
    )

    activities = result["trip"]["days"][0]["activities"]

    assert [activity["name"] for activity in activities] == [
        "Activity 2",
        "Activity 1",
    ]

    assert mock_repair_fn.await_count >= 1


@pytest.mark.anyio
async def test_graph_rejects_unresolved_opening_hours_conflicts(
    monkeypatch,
):
    trip = make_trip()

    async def mock_schedule(
        candidate,
        start_time="09:00",
        origin=None,
    ):
        return candidate

    async def mock_validation(candidate):
        candidate.days[0].activities[0].opening_hours_status = "conflict"
        return candidate

    async def mock_repair(candidate, origin=None):
        return candidate

    monkeypatch.setattr(
        travel_graph,
        "resolve_trip_origin",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        travel_graph,
        "add_itinerary_schedule",
        mock_schedule,
    )
    monkeypatch.setattr(
        travel_graph,
        "validate_itinerary_opening_hours",
        mock_validation,
    )
    monkeypatch.setattr(
        travel_graph,
        "repair_opening_hours_conflicts",
        mock_repair,
    )

    with pytest.raises(
        ValueError,
        match="Could not create an itinerary without opening-hours conflicts",
    ):
        await travel_graph.schedule_node(
            {
                "trip": trip.model_dump(),
                "preferences": TravelPreferences(
                    destination="Chiang Mai, Thailand",
                    duration_days=1,
                    interests=["nature"],
                ),
            }
        )


@pytest.mark.anyio
async def test_optimize_node_enriches_trip(monkeypatch):
    from app import travel_graph
    from app.schemas import TravelItinerary, TravelPreferences

    preferences = TravelPreferences(
        destination="Chiang Mai",
        duration_days=1,
        interests=["nature"],
    )

    trip = TravelItinerary.model_validate(
        {
            "destination": "Chiang Mai",
            "days": [
                {
                    "day": 1,
                    "activities": [],
                }
            ],
        }
    )

    calls = []

    async def fake_enrich(candidate, received_preferences, recommendations):
        calls.append(True)
        assert received_preferences is preferences
        assert recommendations == []
        return candidate

    monkeypatch.setattr(
        travel_graph,
        "enrich_trip_plan",
        fake_enrich,
    )

    result = await travel_graph.optimize_node(
        {
            "trip": trip.model_dump(),
            "preferences": preferences,
            "recommendations": [],
        }
    )

    assert calls == [True]
    assert len(result["trip"]["days"]) == 1
