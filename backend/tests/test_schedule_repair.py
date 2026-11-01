from unittest.mock import AsyncMock

import pytest

from app import schedule_repair
from app.schemas import TravelItinerary


def make_trip():
    return TravelItinerary.model_validate(
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
                            "opening_hours_status": "verified",
                        },
                        {
                            "name": "Activity 2",
                            "activity_type": "hiking",
                            "description": "Second activity",
                            "source_indices": [1],
                            "duration_type": "short",
                            "opening_hours_status": "conflict",
                        },
                    ],
                }
            ],
        }
    )


@pytest.mark.anyio
async def test_repair_swaps_activities_when_conflicts_improve(monkeypatch):
    trip = make_trip()

    async def mock_schedule(candidate, origin=None):
        return candidate

    async def mock_validation(candidate):
        candidate.days[0].activities[0].opening_hours_status = "verified"
        candidate.days[0].activities[1].opening_hours_status = "verified"
        return candidate

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
        lambda candidate: [],
    )

    result = await schedule_repair.repair_opening_hours_conflicts(trip)

    assert [activity.name for activity in result.days[0].activities] == [
        "Activity 2",
        "Activity 1",
    ]
    assert schedule_repair.count_opening_hours_conflicts(result) == 0

    assert [activity.name for activity in trip.days[0].activities] == [
        "Activity 1",
        "Activity 2",
    ]


@pytest.mark.anyio
async def test_repair_rejects_swap_with_excessive_driving(monkeypatch):
    trip = make_trip()

    async def mock_schedule(candidate, origin=None):
        return candidate

    async def mock_validation(candidate):
        for activity in candidate.days[0].activities:
            activity.opening_hours_status = "verified"
        return candidate

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
        AsyncMock(return_value=trip),
    )
    monkeypatch.setattr(
        schedule_repair,
        "find_driving_issues",
        lambda candidate: ["Driving limit exceeded"],
    )
    monkeypatch.setattr(
        schedule_repair,
        "find_total_driving_issues",
        lambda candidate: [],
    )

    result = await schedule_repair.repair_opening_hours_conflicts(trip)

    assert [activity.name for activity in result.days[0].activities] == [
        "Activity 1",
        "Activity 2",
    ]
    assert schedule_repair.count_opening_hours_conflicts(result) == 1
