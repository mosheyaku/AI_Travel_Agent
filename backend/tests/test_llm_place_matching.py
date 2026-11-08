import json

import pytest

from app import llm_place_matching
from app.google_places import GooglePlace


@pytest.mark.anyio
async def test_matches_alternative_place_name(monkeypatch):
    places = [
        GooglePlace(
            place_id="waterfall-123",
            name="Buatong Waterfall",
            latitude=19.0,
            longitude=99.0,
            types=["tourist_attraction"],
        )
    ]

    async def fake_generate_text(prompt):
        return json.dumps({"place_id": "waterfall-123"})

    monkeypatch.setattr(
        llm_place_matching,
        "generate_text",
        fake_generate_text,
    )

    result = await llm_place_matching.match_place_with_llm(
        "Bua Thong Sticky Waterfalls",
        "Chiang Mai, Thailand",
        places,
    )

    assert result is not None
    assert result.place_id == "waterfall-123"


@pytest.mark.anyio
async def test_rejects_unknown_place_id(monkeypatch):
    places = [
        GooglePlace(
            place_id="real-place",
            name="Some Attraction",
            latitude=19.0,
            longitude=99.0,
        )
    ]

    async def fake_generate_text(prompt):
        return json.dumps({"place_id": "invented-place"})

    monkeypatch.setattr(
        llm_place_matching,
        "generate_text",
        fake_generate_text,
    )

    result = await llm_place_matching.match_place_with_llm(
        "Some Attraction",
        "Chiang Mai, Thailand",
        places,
    )

    assert result is None


@pytest.mark.anyio
async def test_rejects_generic_rafting_provider(monkeypatch):
    places = [
        GooglePlace(
            place_id="rafting-provider",
            name="Siam River Adventures",
            latitude=18.79,
            longitude=98.99,
            types=["point_of_interest"],
        )
    ]

    async def fake_generate_text(prompt):
        assert "select a provider only if that provider is explicitly named" in prompt
        return json.dumps({"place_id": None})

    monkeypatch.setattr(
        llm_place_matching,
        "generate_text",
        fake_generate_text,
    )

    result = await llm_place_matching.match_place_with_llm(
        "Whitewater Rafting on the Mae Taeng River",
        "Chiang Mai, Thailand",
        places,
    )

    assert result is None


@pytest.mark.anyio
async def test_guided_tour_matching_requires_departure_evidence(monkeypatch):
    places = [
        GooglePlace(
            place_id="park",
            name="Doi Inthanon National Park",
            latitude=18.588,
            longitude=98.487,
            types=["national_park"],
        )
    ]

    async def fake_generate_text(prompt):
        assert "Booking type: guided_tour" in prompt
        assert "several locations" in prompt
        assert "Do not treat one tour stop as the meeting point" in prompt
        return json.dumps({"place_id": None})

    monkeypatch.setattr(
        llm_place_matching,
        "generate_text",
        fake_generate_text,
    )

    result = await llm_place_matching.match_place_with_llm(
        "Doi Inthanon Guided Tour",
        "Chiang Mai, Thailand",
        places,
        description="A guided tour visiting several locations.",
        booking_type="guided_tour",
    )

    assert result is None
