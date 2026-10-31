from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app import google_places


@pytest.mark.anyio
async def test_get_place_opening_hours(monkeypatch):
    response = MagicMock()
    response.json.return_value = {
        "id": "test-place",
        "regularOpeningHours": {
            "weekdayDescriptions": [
                "Monday: 9:00 AM – 5:00 PM",
                "Tuesday: Closed",
            ]
        },
    }
    response.raise_for_status.return_value = None

    client = AsyncMock()
    client.get.return_value = response

    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=client)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        google_places.httpx,
        "AsyncClient",
        MagicMock(return_value=context_manager),
    )

    result = await google_places.get_place_opening_hours(
        "test-place"
    )

    assert result.place_id == "test-place"
    assert result.weekday_descriptions == [
        "Monday: 9:00 AM – 5:00 PM",
        "Tuesday: Closed",
    ]

    client.get.assert_awaited_once()


@pytest.mark.anyio
async def test_missing_opening_hours(monkeypatch):
    response = MagicMock()
    response.json.return_value = {"id": "test-place"}
    response.raise_for_status.return_value = None

    client = AsyncMock()
    client.get.return_value = response

    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=client)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        google_places.httpx,
        "AsyncClient",
        MagicMock(return_value=context_manager),
    )

    result = await google_places.get_place_opening_hours(
        "test-place"
    )

    assert result.weekday_descriptions == []


@pytest.mark.anyio
async def test_rejects_invalid_place_id():
    with pytest.raises(ValueError):
        await google_places.get_place_opening_hours(
            "invalid/place/id"
        )