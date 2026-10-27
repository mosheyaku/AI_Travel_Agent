import httpx
import pytest

from app import attraction_locations
from app.geocoding import LocationCandidate
from app.google_places import GooglePlace
from app.location_validation import LocationStatus
from app.schemas import AttractionRecommendation


def make_location(name, lat, lon):
    return LocationCandidate(
        name=name,
        latitude=lat,
        longitude=lon,
        osm_type="node",
        osm_id=1,
    )


def make_recommendation(name, category="nature"):
    return AttractionRecommendation(
        name=name,
        category=category,
        description="An attraction.",
        relevance_reason="Matches the user's interests.",
        source_indices=[1],
    )

@pytest.mark.anyio
async def test_filters_distant_attraction(monkeypatch):
    recommendation = make_recommendation("Bangkok Park")

    async def fake_search_locations(name, destination):
        return [
            make_location(
                "Chiang Mai City Municipality, Thailand",
                18.7883,
                98.9853,
            )
        ]

    async def fake_search_google_places(name, destination):
        return [
            GooglePlace(
                place_id="bangkok-park",
                name="Bangkok Park",
                latitude=13.7563,
                longitude=100.5018,
            )
        ]

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert result == []


@pytest.mark.anyio
async def test_keeps_unverified_attraction(monkeypatch):
    recommendation = make_recommendation("Unknown Park")

    async def fake_search_locations(name, destination):
        return [
            make_location(
                "Chiang Mai City Municipality, Thailand",
                18.7883,
                98.9853,
            )
        ]

    async def fake_search_google_places(name, destination):
        return []

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.UNVERIFIED
    assert result[0].latitude is None
    assert result[0].longitude is None
    assert result[0].distance_km is None
    assert result[0].google_place_id is None


@pytest.mark.anyio
async def test_keeps_recommendation_when_geocoding_fails(monkeypatch):
    recommendation = make_recommendation(
        "Elephant Nature Park",
        category="wildlife",
    )

    async def fake_search_locations(name, destination):
        raise httpx.ConnectError("Geocoding service unavailable")

    async def fake_search_google_places(name, destination):
        pytest.fail(
            "Google Places should not be called when destination lookup fails."
        )

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.UNVERIFIED


@pytest.mark.anyio
async def test_keeps_recommendation_when_google_places_fails(monkeypatch):
    recommendation = make_recommendation(
        "Elephant Nature Park",
        category="wildlife",
    )

    async def fake_search_locations(name, destination):
        return [
            make_location(
                "Chiang Mai City Municipality, Thailand",
                18.7883,
                98.9853,
            )
        ]

    async def fake_search_google_places(name, destination):
        raise httpx.ConnectError("Google Places unavailable")

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.UNVERIFIED
    assert result[0].latitude is None


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


@pytest.mark.anyio
async def test_verifies_google_place(monkeypatch):
    recommendation = make_recommendation(
        "Elephant Nature Park",
        category="wildlife",
    )

    async def fake_search_locations(name, destination):
        return [
            make_location(
                "Chiang Mai City Municipality, Thailand",
                18.7882778,
                98.9858802,
            )
        ]

    async def fake_search_google_places(name, destination):
        return [
            GooglePlace(
                place_id="elephant-nature-park",
                name="Elephant Nature Park",
                latitude=19.214683,
                longitude=98.8616387,
            )
        ]

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.VERIFIED
    assert result[0].latitude == 19.214683
    assert result[0].longitude == 98.8616387
    assert result[0].distance_km is not None
    assert result[0].google_place_id == "elephant-nature-park"


@pytest.mark.anyio
async def test_rejects_different_google_place_name(monkeypatch):
    recommendation = make_recommendation(
        "Pongyang Adventure Park",
        category="adventure",
    )

    async def fake_search_locations(name, destination):
        return [
            make_location(
                "Chiang Mai City Municipality, Thailand",
                18.7883,
                98.9853,
            )
        ]

    async def fake_search_google_places(name, destination):
        return [
            GooglePlace(
                place_id="pong-yang",
                name="Pong Yang Jungle Coaster & Zipline",
                latitude=18.9168336,
                longitude=98.821529,
            )
        ]

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.UNVERIFIED
    assert result[0].latitude is None
    assert result[0].longitude is None
    assert result[0].distance_km is None


@pytest.mark.anyio
async def test_verifies_attraction_using_alternative_name(monkeypatch):
    recommendation = make_recommendation(
        "Sticky Waterfall (Bua Thong Waterfall)"
    )

    async def fake_search_locations(name, destination):
        return [
            make_location(
                "Chiang Mai City Municipality, Thailand",
                18.7883,
                98.9853,
            )
        ]

    searched_names = []

    async def fake_search_google_places(name, destination):
        searched_names.append(name)

        if name == "Sticky Waterfall":
            return []

        if name == "Bua Thong Waterfall":
            return [
                GooglePlace(
                    place_id="bua-thong",
                    name="Bua Thong Waterfall",
                    latitude=19.069,
                    longitude=99.079,
                    types=["tourist_attraction"],
                )
            ]

        return []

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert searched_names == [
        "Sticky Waterfall",
        "Bua Thong Waterfall",
    ]

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.VERIFIED
    assert result[0].latitude == 19.069
    assert result[0].longitude == 99.079
    assert result[0].distance_km is not None



@pytest.mark.anyio
async def test_stops_searching_after_first_match(monkeypatch):
    recommendation = make_recommendation(
        "Sticky Waterfall (Bua Thong Waterfall)"
    )

    async def fake_search_locations(name, destination):
        return [
            make_location(
                "Chiang Mai City Municipality, Thailand",
                18.7883,
                98.9853,
            )
        ]

    searched_names = []

    async def fake_search_google_places(name, destination):
        searched_names.append(name)

        return [
            GooglePlace(
                place_id="sticky-waterfall",
                name="Sticky Waterfall",
                latitude=19.069,
                longitude=99.079,
                types=["tourist_attraction"],
            )
        ]

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert searched_names == ["Sticky Waterfall"]
    assert len(result) == 1
    assert result[0].location_status == LocationStatus.VERIFIED



@pytest.mark.anyio
async def test_does_not_verify_travel_agency(monkeypatch):
    recommendation = make_recommendation(
        "Elephant Sanctuary Office",
        category="wildlife",
    )

    async def fake_search_locations(name, destination):
        return [
            make_location(
                "Chiang Mai City Municipality, Thailand",
                18.7883,
                98.9853,
            )
        ]

    async def fake_search_google_places(name, destination):
        return [
            GooglePlace(
                place_id="elephant-office",
                name="Elephant Sanctuary Office",
                latitude=18.7863,
                longitude=98.9904,
                types=[
                    "tour_agency",
                    "travel_agency",
                    "point_of_interest",
                ],
            )
        ]

    monkeypatch.setattr(
        attraction_locations,
        "search_locations",
        fake_search_locations,
    )
    monkeypatch.setattr(
        attraction_locations,
        "search_google_places",
        fake_search_google_places,
    )

    result = await attraction_locations.validate_attraction_locations(
        [recommendation],
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].location_status == LocationStatus.UNVERIFIED
    assert result[0].latitude is None
    assert result[0].longitude is None
    assert result[0].distance_km is None