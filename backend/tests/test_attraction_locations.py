
import pytest

from app import attraction_locations
from app.geocoding import LocationCandidate
from app.schemas import AttractionRecommendation
from app.location_validation import LocationStatus


def make_location(name, lat, lon):
    return LocationCandidate(
        name=name,
        latitude=lat,
        longitude=lon,
        osm_type="node",
        osm_id=1,
    )


@pytest.mark.anyio
async def test_filters_distant_attraction(monkeypatch):
    recommendation = AttractionRecommendation(
        name="Bangkok Park",
        category="nature",
        description="A park.",
        relevance_reason="Nature.",
        source_indices=[1],
    )

    async def fake_search_locations(name, destination):
        if name == "Chiang Mai, Thailand":
            return [
                make_location(
                    "Chiang Mai, Thailand",
                    18.7883,
                    98.9853,
                )
            ]

        return [
            make_location(
                "Bangkok Park, Thailand",
                13.7563,
                100.5018,
            )
        ]

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert result == []


@pytest.mark.anyio
async def test_keeps_unverified_attraction(monkeypatch):
    recommendation = AttractionRecommendation(
        name="Unknown Park",
        category="nature",
        description="A park.",
        relevance_reason="Nature.",
        source_indices=[1],
    )

    async def fake_search_locations(name, destination):
        if name == "Chiang Mai, Thailand":
            return [
                make_location(
                    "Chiang Mai, Thailand",
                    18.7883,
                    98.9853,
                )
            ]

        return []

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.UNVERIFIED
    assert result[0].latitude is None


@pytest.mark.anyio
async def test_keeps_recommendation_when_geocoding_fails(monkeypatch):
    import httpx

    recommendation = AttractionRecommendation(
        name="Elephant Nature Park",
        category="wildlife",
        description="An elephant rescue center.",
        relevance_reason="Matches wildlife interests.",
        source_indices=[1],
    )

    async def fake_search_locations(name, destination):
        if name == "Chiang Mai, Thailand":
            return [
                make_location(
                    "Chiang Mai, Thailand",
                    18.7883,
                    98.9853,
                )
            ]

        raise httpx.ConnectError("Geocoding service unavailable")

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.UNVERIFIED


def test_finds_city_instead_of_province():
    candidates = [
        make_location(
            "Chiang Mai City Municipality, Thailand",
            18.7882778,
            98.9858802,
        ),
        make_location(
            "Chiang Mai Province, Thailand",
            18.6951714,
            98.4462684,
        ),
    ]

    result = attraction_locations.find_destination(
        "Chiang Mai, Thailand",
        candidates,
    )

    assert result == candidates[0]
