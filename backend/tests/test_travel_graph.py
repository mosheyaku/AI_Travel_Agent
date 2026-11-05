from unittest.mock import AsyncMock

import pytest

from app import travel_graph
from app.location_validation import LocationStatus
from app.schemas import TravelItinerary, TravelPreferences
from app import schedule_repair
from app import travel_graph
from app.schemas import TravelItinerary, TravelPreferences
from datetime import date, timedelta


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
    assert mock_evaluate.await_count == 3


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
    mock_evaluate = AsyncMock(
        side_effect=[
            ["Day 1: invalid route"],
            ["Day 1: invalid route"],
            [],
            [],
            [],
        ]
    )
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

    assert mock_recommend.await_count == 2


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

    monkeypatch.setattr(
        travel_graph,
        "repair_trip_plan",
        AsyncMock(return_value=None),
    )

    with pytest.raises(
        ValueError,
        match="could be repaired",
    ):
        await travel_graph.travel_graph.ainvoke(
            {
                "preferences": preferences,
            }
        )


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
        for index, activity in enumerate(candidate.days[0].activities):
            hour = 9 + index
            activity.start_time = f"{hour:02d}:00"
            activity.end_time = f"{hour + 1:02d}:00"
            activity.schedule_status = "estimated"
            activity.timing_status = "estimated"

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
async def test_optimize_node_preserves_base_trip_when_enrichment_fails(
    monkeypatch,
    preferences,
):
    trip = make_trip()
    original = trip.model_dump(mode="json")

    async def fake_enrich(candidate, received_preferences, recommendations):
        candidate.days[0].activities.clear()
        raise ValueError("Enrichment failed")

    monkeypatch.setattr(
        travel_graph,
        "enrich_trip_plan",
        fake_enrich,
    )

    result = await travel_graph.optimize_node(
        {
            "trip": original,
            "preferences": preferences,
            "recommendations": [],
        }
    )

    assert result["base_trip"] == original
    assert result["trip"] == original
    assert len(result["trip"]["days"][0]["activities"]) == 1


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
                if activity.name == "Unschedulable Activity":
                    activity.start_time = None
                    activity.end_time = None
                    activity.schedule_status = "unknown"
                    activity.timing_status = "conflict"
                else:
                    activity.start_time = "09:00"
                    activity.end_time = "10:00"
                    activity.schedule_status = "estimated"
                    activity.timing_status = "estimated"

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
async def test_schedule_rejects_activities_without_schedule(
    monkeypatch,
    preferences,
):
    trip = make_trip()

    async def fake_add_schedule(
        candidate,
        start_time="09:00",
        origin=None,
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
        fake_add_schedule,
    )

    monkeypatch.setattr(
        travel_graph,
        "validate_itinerary_opening_hours",
        AsyncMock(return_value=trip),
    )

    monkeypatch.setattr(
        travel_graph,
        "repair_opening_hours_conflicts",
        AsyncMock(return_value=trip),
    )

    with pytest.raises(
        ValueError,
        match="The itinerary contains unscheduled activities",
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


def test_additional_search_required_for_insufficient_coverage():
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=3,
        interests=["adventure", "nature"],
    )

    recommendations = [
        {
            "name": "Sticky Waterfall",
            "category": "nature",
        }
    ]

    assert travel_graph.needs_additional_search(
        preferences,
        recommendations,
    )

    assert travel_graph.get_missing_interests(
        preferences,
        recommendations,
    ) == ["adventure"]


def test_additional_search_not_required_when_coverage_is_sufficient():
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["adventure", "nature"],
    )

    recommendations = [
        {"name": "Zipline A", "category": "adventure"},
        {"name": "Rafting B", "category": "adventure"},
        {"name": "Waterfall C", "category": "nature"},
        {"name": "National Park D", "category": "nature"},
    ]

    assert not travel_graph.needs_additional_search(
        preferences,
        recommendations,
    )


@pytest.mark.anyio
async def test_recommend_node_expands_verified_attractions(
    monkeypatch,
):
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["nature", "adventure"],
    )

    initial_result = {
        "sources": [
            {
                "title": "Nature Guide",
                "url": "https://example.com/nature",
            }
        ],
        "recommendations": [
            {
                "name": "Sticky Waterfall",
                "category": "nature",
                "activity_type": "waterfall",
                "location_status": LocationStatus.VERIFIED,
                "latitude": 19.1,
                "longitude": 99.0,
                "google_place_id": "place_nature",
                "source_indices": [1],
            }
        ],
    }

    additional_result = {
        "sources": [
            {
                "title": "Adventure Guide",
                "url": "https://example.com/adventure",
            }
        ],
        "recommendations": [
            {
                "name": "Zipline Adventure",
                "category": "adventure",
                "activity_type": "zipline",
                "location_status": LocationStatus.VERIFIED,
                "latitude": 18.8,
                "longitude": 98.9,
                "google_place_id": "place_adventure",
                "source_indices": [1],
            }
        ],
    }

    mock_recommend = AsyncMock(side_effect=[initial_result, additional_result])

    monkeypatch.setattr(
        travel_graph,
        "recommend_attractions",
        mock_recommend,
    )

    result = await travel_graph.recommend_node({"preferences": preferences})

    assert mock_recommend.await_count == 2

    assert len(result["recommendations"]) == 2
    assert len(result["sources"]) == 2

    assert [item["name"] for item in result["recommendations"]] == [
        "Sticky Waterfall",
        "Zipline Adventure",
    ]

    assert result["recommendations"][0]["source_indices"] == [1]
    assert result["recommendations"][1]["source_indices"] == [2]

    additional_queries = mock_recommend.await_args_list[1].args[0]

    assert len(additional_queries) == 1
    assert "adventure" in additional_queries[0]


@pytest.mark.anyio
async def test_recommend_node_preserves_verified_attractions_when_expansion_fails(
    monkeypatch,
):
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["nature", "adventure"],
    )

    initial_result = {
        "sources": [
            {
                "title": "Nature Guide",
                "url": "https://example.com/nature",
            }
        ],
        "recommendations": [
            {
                "name": "Sticky Waterfall",
                "category": "nature",
                "activity_type": "waterfall",
                "location_status": LocationStatus.VERIFIED,
                "latitude": 19.1,
                "longitude": 99.0,
                "google_place_id": "place_nature",
                "source_indices": [1],
            }
        ],
    }

    mock_recommend = AsyncMock(
        side_effect=[
            initial_result,
            TimeoutError("Search timed out"),
        ]
    )

    monkeypatch.setattr(
        travel_graph,
        "recommend_attractions",
        mock_recommend,
    )

    result = await travel_graph.recommend_node({"preferences": preferences})

    assert mock_recommend.await_count == 2

    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["name"] == "Sticky Waterfall"
    assert result["recommendations"][0]["source_indices"] == [1]
    assert len(result["sources"]) == 1


@pytest.mark.anyio
async def test_schedule_without_start_date_uses_consecutive_days(monkeypatch):
    attempted_dates = []

    async def mock_schedule(trip_data, preferences):
        attempted_dates.append(preferences.start_date)

        if preferences.start_date.weekday() != 2:
            raise ValueError("No valid schedule.")

        trip = TravelItinerary.model_validate(trip_data)

        for day in trip.days:
            day.date = preferences.start_date + timedelta(days=day.day - 1)

        return trip

    monkeypatch.setattr(
        travel_graph,
        "_try_schedule_trip_for_date",
        mock_schedule,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai",
        duration_days=3,
        interests=["nature"],
    )

    trip_data = {
        "destination": "Chiang Mai",
        "days": [
            {"day": 1, "activities": []},
            {"day": 2, "activities": []},
            {"day": 3, "activities": []},
        ],
    }

    result = await travel_graph.try_schedule_trip(trip_data, preferences)

    assert len(attempted_dates) == 4
    assert attempted_dates[-1].weekday() == 2
    assert all(day.date is None for day in result.days)


@pytest.mark.anyio
async def test_schedule_with_start_date_does_not_try_other_weekdays(monkeypatch):
    attempted_dates = []

    async def mock_schedule(trip_data, preferences):
        attempted_dates.append(preferences.start_date)
        return TravelItinerary.model_validate(trip_data)

    monkeypatch.setattr(
        travel_graph,
        "_try_schedule_trip_for_date",
        mock_schedule,
    )

    start_date = date(2026, 12, 15)

    preferences = TravelPreferences(
        destination="Chiang Mai",
        duration_days=1,
        start_date=start_date,
        interests=["nature"],
    )

    trip_data = {
        "destination": "Chiang Mai",
        "days": [{"day": 1, "activities": []}],
    }

    await travel_graph.try_schedule_trip(trip_data, preferences)

    assert attempted_dates == [start_date]


@pytest.mark.anyio
async def test_schedule_without_date_respects_consecutive_opening_days(
    monkeypatch,
):
    attempted_dates = []

    async def mock_schedule(trip_data, preferences):
        start_date = preferences.start_date
        attempted_dates.append(start_date)

        first_day = start_date.weekday()
        second_day = (start_date + timedelta(days=1)).weekday()

        # The first activity is available on Monday.
        # The second activity is available on Tuesday.
        if first_day != 0 or second_day != 1:
            raise ValueError("Activities are unavailable on these weekdays.")

        trip = TravelItinerary.model_validate(trip_data)

        for day in trip.days:
            day.date = start_date + timedelta(days=day.day - 1)

            for activity in day.activities:
                activity.start_time = "09:00"
                activity.end_time = "10:30"
                activity.schedule_status = "estimated"
                activity.timing_status = "estimated"
                activity.opening_hours_status = "verified"

        return trip

    monkeypatch.setattr(
        travel_graph,
        "_try_schedule_trip_for_date",
        mock_schedule,
    )

    preferences = TravelPreferences(
        destination="Chiang Mai",
        duration_days=2,
        interests=["nature"],
    )

    trip_data = {
        "destination": "Chiang Mai",
        "days": [
            {
                "day": 1,
                "activities": [
                    {
                        "name": "Monday Activity",
                        "activity_type": "nature",
                        "description": "Available on Monday.",
                        "source_indices": [1],
                    }
                ],
            },
            {
                "day": 2,
                "activities": [
                    {
                        "name": "Tuesday Activity",
                        "activity_type": "nature",
                        "description": "Available on Tuesday.",
                        "source_indices": [1],
                    }
                ],
            },
        ],
    }

    result = await travel_graph.try_schedule_trip(
        trip_data,
        preferences,
    )

    assert len(attempted_dates) == 2
    assert attempted_dates[0].weekday() == 6
    assert attempted_dates[1].weekday() == 0

    assert all(day.date is None for day in result.days)

    assert all(
        activity.opening_hours_status == "unknown"
        for day in result.days
        for activity in day.activities
    )

    assert all(
        activity.start_time == "09:00" and activity.end_time == "10:30"
        for day in result.days
        for activity in day.activities
    )
