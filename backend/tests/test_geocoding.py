from unittest.mock import AsyncMock

import httpx
import pytest

from app import geocoding


@pytest.mark.anyio
async def test_search_locations_returns_candidates(monkeypatch):
    geocoding._cache.clear()

    response = httpx.Response(
        200,
        json=[
            {
                "display_name": "Elephant Nature Park, Chiang Mai, Thailand",
                "lat": "19.215",
                "lon": "98.858",
                "osm_type": "way",
                "osm_id": 12345,
            }
        ],
        request=httpx.Request("GET", geocoding.NOMINATIM_URL),
    )

    mock_get = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await geocoding.search_locations(
        "Elephant Nature Park",
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].latitude == 19.215
    assert result[0].longitude == 98.858
    assert result[0].osm_id == 12345


@pytest.mark.anyio
async def test_search_locations_returns_empty_list(monkeypatch):
    geocoding._cache.clear()

    response = httpx.Response(
        200,
        json=[],
        request=httpx.Request("GET", geocoding.NOMINATIM_URL),
    )

    mock_get = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await geocoding.search_locations(
        "Unknown Attraction",
        "Chiang Mai, Thailand",
    )

    assert result == []


@pytest.mark.anyio
async def test_search_locations_uses_cache(monkeypatch):
    geocoding._cache.clear()

    response = httpx.Response(
        200,
        json=[],
        request=httpx.Request("GET", geocoding.NOMINATIM_URL),
    )

    mock_get = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    await geocoding.search_locations("Test Park", "Chiang Mai")
    await geocoding.search_locations("Test Park", "Chiang Mai")

    assert mock_get.await_count == 1
