import json
from unittest.mock import AsyncMock

import pytest

import app.duration_enrichment as duration_enrichment
from app.duration_enrichment import enrich_attraction_duration


def make_attraction(
    name: str = "Skyline Adventure",
    duration_type: str = "full_day",
    duration_minutes: int | None = None,
) -> dict:
    return {
        "name": name,
        "activity_type": "zipline",
        "duration_type": duration_type,
        "duration_minutes": duration_minutes,
    }


def mock_duration_sources(monkeypatch, content: str) -> None:
    monkeypatch.setattr(
        duration_enrichment,
        "search_attractions",
        lambda query: {
            "results": [
                {
                    "title": "Attraction information",
                    "url": "https://example.com/attraction",
                    "content": content,
                }
            ]
        },
    )


def mock_duration_response(
    monkeypatch,
    duration_type: str,
    duration_minutes: int | None,
    quote: str,
) -> None:
    monkeypatch.setattr(
        duration_enrichment,
        "generate_text",
        AsyncMock(
            return_value=json.dumps(
                {
                    "duration_type": duration_type,
                    "duration_minutes": duration_minutes,
                    "evidence": [
                        {
                            "source_index": 1,
                            "quote": quote,
                        }
                    ],
                }
            )
        ),
    )


@pytest.mark.anyio
async def test_exact_duration_corrects_inconsistent_type():
    attraction = make_attraction(duration_minutes=120)

    result = await enrich_attraction_duration(
        attraction,
        "Chiang Mai, Thailand",
    )

    assert result["duration_minutes"] == 120
    assert result["duration_type"] == "short"


@pytest.mark.anyio
async def test_unsupported_full_day_becomes_unknown(monkeypatch):
    attraction = make_attraction()

    mock_duration_sources(
        monkeypatch,
        "Skyline Adventure offers zipline activities.",
    )

    monkeypatch.setattr(
        duration_enrichment,
        "generate_text",
        AsyncMock(
            return_value=json.dumps(
                {
                    "duration_type": "unknown",
                    "duration_minutes": None,
                    "evidence": [],
                }
            )
        ),
    )

    result = await enrich_attraction_duration(
        attraction,
        "Chiang Mai, Thailand",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_missing_duration_sources_becomes_unknown(monkeypatch):
    monkeypatch.setattr(
        duration_enrichment,
        "search_attractions",
        lambda query: {"results": []},
    )

    result = await enrich_attraction_duration(
        make_attraction(),
        "Chiang Mai, Thailand",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_invalid_duration_response_becomes_unknown(monkeypatch):
    mock_duration_sources(
        monkeypatch,
        "Skyline Adventure offers zipline activities.",
    )

    monkeypatch.setattr(
        duration_enrichment,
        "generate_text",
        AsyncMock(return_value="invalid JSON"),
    )

    result = await enrich_attraction_duration(
        make_attraction(),
        "Chiang Mai, Thailand",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_source_supported_duration_label_is_preserved(monkeypatch):
    quote = "Example Waterfall half-day guided experience is available."

    mock_duration_sources(monkeypatch, quote)

    mock_duration_response(
        monkeypatch,
        duration_type="half_day",
        duration_minutes=None,
        quote=quote,
    )

    result = await enrich_attraction_duration(
        make_attraction(name="Example Waterfall"),
        "Chiang Mai",
    )

    assert result["duration_type"] == "half_day"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_exact_supported_duration_is_accepted(monkeypatch):
    quote = "Skyline Adventure zipline experience lasts 3 hours."

    mock_duration_sources(monkeypatch, quote)

    mock_duration_response(
        monkeypatch,
        duration_type="half_day",
        duration_minutes=180,
        quote=quote,
    )

    result = await enrich_attraction_duration(
        make_attraction(),
        "Chiang Mai",
    )

    assert result["duration_type"] == "half_day"
    assert result["duration_minutes"] == 180


@pytest.mark.anyio
async def test_unsupported_exact_duration_is_rejected(monkeypatch):
    quote = "Skyline Adventure zipline experience lasts 3 hours."

    mock_duration_sources(monkeypatch, quote)

    mock_duration_response(
        monkeypatch,
        duration_type="half_day",
        duration_minutes=240,
        quote=quote,
    )

    result = await enrich_attraction_duration(
        make_attraction(),
        "Chiang Mai",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_nonexistent_evidence_quote_is_rejected(monkeypatch):
    mock_duration_sources(
        monkeypatch,
        "Skyline Adventure offers zipline activities.",
    )

    mock_duration_response(
        monkeypatch,
        duration_type="half_day",
        duration_minutes=180,
        quote="Skyline Adventure experience lasts 3 hours.",
    )

    result = await enrich_attraction_duration(
        make_attraction(),
        "Chiang Mai",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_opening_hours_are_not_visit_duration(monkeypatch):
    quote = "Skyline Adventure opening hours are 8 hours per day."

    mock_duration_sources(monkeypatch, quote)

    mock_duration_response(
        monkeypatch,
        duration_type="full_day",
        duration_minutes=480,
        quote=quote,
    )

    result = await enrich_attraction_duration(
        make_attraction(),
        "Chiang Mai",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_duration_range_does_not_produce_exact_minutes(monkeypatch):
    quote = "Skyline Adventure zipline experience lasts 3 to 4 hours."

    mock_duration_sources(monkeypatch, quote)

    mock_duration_response(
        monkeypatch,
        duration_type="half_day",
        duration_minutes=180,
        quote=quote,
    )

    result = await enrich_attraction_duration(
        make_attraction(),
        "Chiang Mai",
    )

    assert result["duration_type"] == "unknown"
    assert result["duration_minutes"] is None


@pytest.mark.anyio
async def test_results_preserve_original_order(monkeypatch):
    attractions = [
        make_attraction(name="First Attraction", duration_minutes=60),
        make_attraction(name="Second Attraction", duration_minutes=180),
        make_attraction(name="Third Attraction", duration_minutes=480),
    ]

    results = await duration_enrichment.enrich_attraction_durations(
        attractions,
        "Chiang Mai",
    )

    assert [item["name"] for item in results] == [
        "First Attraction",
        "Second Attraction",
        "Third Attraction",
    ]

    assert [item["duration_type"] for item in results] == [
        "short",
        "half_day",
        "full_day",
    ]
