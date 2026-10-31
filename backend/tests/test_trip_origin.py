from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app import trip_generator
from app.schemas import TravelPreferences


def make_preferences(**overrides):
    data = {
        "destination": "Chiang Mai, Thailand",
        "duration_days": 3,
        "interests": ["adventure", "nature"],
        "pace": "balanced",
    }
    data.update(overrides)
    return TravelPreferences.model_validate(data)


def test_accepts_accommodation_coordinates():
    preferences = make_preferences(
        accommodation_latitude=18.79,
        accommodation_longitude=98.98,
    )

    assert preferences.accommodation_latitude == 18.79
    assert preferences.accommodation_longitude == 98.98


def test_rejects_incomplete_accommodation_coordinates():
    with pytest.raises(ValidationError):
        make_preferences(accommodation_latitude=18.79)


def test_rejects_invalid_accommodation_coordinates():
    with pytest.raises(ValidationError):
        make_preferences(
            accommodation_latitude=100,
            accommodation_longitude=98.98,
        )


@pytest.mark.anyio
async def test_uses_accommodation_as_trip_origin(monkeypatch):
    mock_find_origin = AsyncMock()

    monkeypatch.setattr(
        trip_generator,
        "find_trip_origin",
        mock_find_origin,
    )

    preferences = make_preferences(
        accommodation_latitude=18.79,
        accommodation_longitude=98.98,
    )

    result = await trip_generator.resolve_trip_origin(preferences)

    assert result == (18.79, 98.98)
    mock_find_origin.assert_not_awaited()


@pytest.mark.anyio
async def test_falls_back_to_destination_center(monkeypatch):
    mock_find_origin = AsyncMock(return_value=(18.78, 98.99))

    monkeypatch.setattr(
        trip_generator,
        "find_trip_origin",
        mock_find_origin,
    )

    preferences = make_preferences()

    result = await trip_generator.resolve_trip_origin(preferences)

    assert result == (18.78, 98.99)
    mock_find_origin.assert_awaited_once_with("Chiang Mai, Thailand")
