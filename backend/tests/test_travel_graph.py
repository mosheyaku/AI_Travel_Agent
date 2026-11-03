from unittest.mock import AsyncMock

import pytest

from app import travel_graph
from app.location_validation import LocationStatus
from app.schemas import TravelItinerary, TravelPreferences
from app import schedule_repair


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
    for recommendation in recommendations:
        recommendation["location_status"] = LocationStatus.UNVERIFIED

    mock_recommend = AsyncMock(
        return_value={
            "recommendations": recommendations,
            "sources": [],
        }
    )

    monkeypatch.setattr(
        travel_graph,
        "recommend_attractions",
        mock_recommend,
    )

    with pytest.raises(
        ValueError,
        match="No attractions with verified locations",
    ):
        await travel_graph.travel_graph.ainvoke({"preferences": preferences})

    mock_recommend.assert_awaited_once()


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

    async def mock_repair(
        candidate,
        origin=None,
        start_time="09:00",
    ):
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

    async def mock_repair(
        candidate,
        origin=None,
        start_time="09:00",
    ):
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
        match="Could not schedule either itinerary",
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


@pytest.mark.anyio
async def test_graph_preserves_valid_activity_after_schedule_conflict(
    monkeypatch,
):
    trip = TravelItinerary.model_validate(
        {
            "destination": "Chiang Mai, Thailand",
            "days": [
                {
                    "day": 1,
                    "activities": [
                        {
                            "name": "Unschedulable Activity",
                            "activity_type": "hiking",
                            "description": "Cannot fit the schedule.",
                            "source_indices": [1],
                            "duration_type": "short",
                        },
                        {
                            "name": "Valid Activity",
                            "activity_type": "hiking",
                            "description": "Fits the schedule.",
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
        for day in candidate.days:
            for activity in day.activities:
                activity.timing_status = (
                    "conflict"
                    if activity.name == "Unschedulable Activity"
                    else "estimated"
                )
        return candidate

    async def mock_validation(candidate):
        for day in candidate.days:
            for activity in day.activities:
                activity.opening_hours_status = "verified"
        return candidate

    async def mock_routes(candidate):
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
        schedule_repair,
        "add_itinerary_schedule",
        mock_schedule,
    )
    monkeypatch.setattr(
        schedule_repair,
        "validate_itinerary_opening_hours",
        mock_validation,
    )
    monkeypatch.setattr(
        schedule_repair,
        "add_driving_routes",
        mock_routes,
    )
    monkeypatch.setattr(
        schedule_repair,
        "find_driving_issues",
        lambda candidate: [],
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

    assert len(activities) == 1
    assert activities[0]["name"] == "Valid Activity"
    assert activities[0]["timing_status"] != "conflict"


@pytest.mark.anyio
async def test_schedule_falls_back_to_base_trip(monkeypatch, preferences):
    base_trip = make_trip()

    optimized_trip = base_trip.model_copy(deep=True)
    optimized_trip.days[0].activities[0].name = "Broken Activity"

    attempts = []

    async def mock_try_schedule(trip_data, received_preferences):
        assert received_preferences is preferences

        candidate = TravelItinerary.model_validate(trip_data)
        name = candidate.days[0].activities[0].name
        attempts.append(name)

        if name == "Broken Activity":
            raise ValueError("Scheduling failed")

        return candidate

    monkeypatch.setattr(
        travel_graph,
        "try_schedule_trip",
        mock_try_schedule,
    )

    result = await travel_graph.schedule_node(
        {
            "trip": optimized_trip.model_dump(mode="json"),
            "base_trip": base_trip.model_dump(mode="json"),
            "preferences": preferences,
        }
    )

    assert attempts == ["Broken Activity", "Test Park"]
    assert result["trip"]["days"][0]["activities"][0]["name"] == "Test Park"


@pytest.mark.anyio
async def test_schedule_fails_when_both_candidates_fail(
    monkeypatch,
    preferences,
):
    trip = make_trip()

    mock_try_schedule = AsyncMock(side_effect=ValueError("Scheduling failed"))

    monkeypatch.setattr(
        travel_graph,
        "try_schedule_trip",
        mock_try_schedule,
    )

    with pytest.raises(
        ValueError,
        match="Could not schedule either itinerary",
    ):
        await travel_graph.schedule_node(
            {
                "trip": trip.model_dump(mode="json"),
                "base_trip": trip.model_dump(mode="json"),
                "preferences": preferences,
            }
        )

    assert mock_try_schedule.await_count == 2


@pytest.mark.anyio
async def test_schedule_rejects_empty_days(monkeypatch, preferences):
    trip = TravelItinerary.model_validate(
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
                },
                {
                    "day": 2,
                    "activities": [],
                },
            ],
        }
    )

    monkeypatch.setattr(
        travel_graph,
        "resolve_trip_origin",
        AsyncMock(return_value=None),
    )

    monkeypatch.setattr(
        travel_graph,
        "fill_empty_days",
        AsyncMock(return_value=trip),
    )

    with pytest.raises(
        ValueError,
        match="The itinerary contains empty days",
    ):
        await travel_graph.try_schedule_trip(
            trip.model_dump(mode="json"),
            preferences,
        )


@pytest.mark.anyio
async def test_rebuild_schedule_does_not_reject_unrelated_driving_issues(
    monkeypatch,
):
    trip = make_trip()

    monkeypatch.setattr(
        schedule_repair,
        "add_driving_routes",
        AsyncMock(return_value=trip),
    )
    monkeypatch.setattr(
        schedule_repair,
        "add_total_driving_routes",
        AsyncMock(return_value=trip),
    )
    monkeypatch.setattr(
        schedule_repair,
        "add_itinerary_schedule",
        AsyncMock(return_value=trip),
    )
    monkeypatch.setattr(
        schedule_repair,
        "validate_itinerary_opening_hours",
        AsyncMock(return_value=trip),
    )
    monkeypatch.setattr(
        schedule_repair,
        "find_driving_issues",
        lambda candidate: [],
    )
    monkeypatch.setattr(
        schedule_repair,
        "find_total_driving_issues",
        lambda candidate: ["Unrelated total driving issue"],
    )

    result = await schedule_repair.rebuild_schedule(
        trip,
        origin=(18.7, 98.9),
    )

    assert result is not None
