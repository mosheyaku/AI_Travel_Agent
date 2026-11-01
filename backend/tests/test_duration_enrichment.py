import pytest

from app.duration_enrichment import enrich_attraction_duration
from unittest.mock import AsyncMock

import app.duration_enrichment as duration_enrichment


@pytest.mark.anyio
async def test_exact_duration_corrects_inconsistent_type():
    attraction = {
        "name": "Skyline Adventure",
        "activity_type": "zipline",
        "duration_type": "full_day",
        "duration_minutes": 120,
    }

    result = await enrich_attraction_duration(
        attraction,
        "Chiang Mai, Thailand",
    )

    assert result["duration_minutes"] == 120
    assert result["duration_type"] == "short"


@pytest.mark.anyio
async def test_unsupported_full_day_becomes_unknown(monkeypatch):
    attraction = {
        "name": "Skyline Adventure",
        "activity_type": "zipline",
        "duration_type": "full_day",
        "duration_minutes": None,
    }

    monkeypatch.setattr(
        duration_enrichment,
        "search_attractions",
        lambda query: {
            "results": [
                {
                    "title": "Skyline Adventure",
                    "url": "https://example.com/skyline",
                    "content": "Skyline Adventure offers zipline activities.",
                }
            ]
        },
    )

    monkeypatch.setattr(
        duration_enrichment,
        "generate_text",
        AsyncMock(
            return_value='{"duration_type": "unknown", '
            '"duration_minutes": null, "source_indices": []}'
        ),
    )

    result = await duration_enrichment.enrich_attraction_duration(
        attraction,
        "Chiang Mai, Thailand",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_missing_duration_sources_becomes_unknown(monkeypatch):
    attraction = {
        "name": "Skyline Adventure",
        "activity_type": "zipline",
        "duration_type": "full_day",
        "duration_minutes": None,
    }

    monkeypatch.setattr(
        duration_enrichment,
        "search_attractions",
        lambda query: {"results": []},
    )

    result = await duration_enrichment.enrich_attraction_duration(
        attraction,
        "Chiang Mai, Thailand",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_invalid_duration_response_becomes_unknown(monkeypatch):
    attraction = {
        "name": "Skyline Adventure",
        "activity_type": "zipline",
        "duration_type": "full_day",
        "duration_minutes": None,
    }

    monkeypatch.setattr(
        duration_enrichment,
        "search_attractions",
        lambda query: {
            "results": [
                {
                    "title": "Skyline Adventure",
                    "url": "https://example.com/skyline",
                    "content": "Skyline Adventure offers zipline activities.",
                }
            ]
        },
    )

    monkeypatch.setattr(
        duration_enrichment,
        "generate_text",
        AsyncMock(return_value="invalid JSON"),
    )

    result = await duration_enrichment.enrich_attraction_duration(
        attraction,
        "Chiang Mai, Thailand",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_source_supported_duration_label_is_preserved(monkeypatch):
    from unittest.mock import AsyncMock
    import app.duration_enrichment as duration_enrichment

    attraction = {
        "name": "Example Waterfall",
        "activity_type": "waterfall",
        "duration_type": "full_day",
        "duration_minutes": None,
    }
    monkeypatch.setattr(duration_enrichment, "search_attractions", lambda query: {
        "results": [{"title": "Example Waterfall", "url": "https://example.com",
                     "content": "Example Waterfall is in the national park."}]
    })
    monkeypatch.setattr(duration_enrichment, "generate_text", AsyncMock(
        return_value='{"duration_type":"half_day","duration_minutes":null,"source_indices":[1]}'
    ))
    result = await duration_enrichment.enrich_attraction_duration(attraction, "Chiang Mai")
    assert result["duration_type"] == "half_day"
    assert result["duration_minutes"] is None
