import pytest

from app.geocoding import LocationCandidate
from app.location_validation import (
    LocationStatus,
    calculate_distance_km,
    matches_attraction_name,
    validate_location,
)


def make_location(name: str, lat: float, lon: float) -> LocationCandidate:
    return LocationCandidate(
        name=name,
        latitude=lat,
        longitude=lon,
        osm_type="node",
        osm_id=1,
    )


def test_distance_between_same_coordinates_is_zero():
    assert calculate_distance_km(18.7883, 98.9853, 18.7883, 98.9853) == 0


def test_distance_between_known_cities():
    distance = calculate_distance_km(
        18.7883, 98.9853,
        13.7563, 100.5018,
    )

    assert 580 < distance < 600


def test_accepts_attraction_within_range():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)
    attraction = make_location("Nearby Park", 18.9, 99.0)

    result = validate_location(destination, [attraction], attraction_name="Nearby Park",)

    assert result.status == LocationStatus.VERIFIED
    assert result.distance_km is not None
    assert result.distance_km < 150


def test_rejects_attraction_outside_range():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)
    attraction = make_location("Bangkok Park", 13.7563, 100.5018)

    result = validate_location(destination, [attraction],attraction_name="Bangkok Park")

    assert result.status == LocationStatus.OUT_OF_RANGE
    assert result.distance_km is not None
    assert result.distance_km > 150


def test_unverified_when_no_candidates():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)

    result = validate_location(destination, [], attraction_name="Unknown Park")

    assert result.status == LocationStatus.UNVERIFIED
    assert result.location is None


def test_unverified_when_multiple_candidates():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)

    candidates = [
        make_location("Park A", 18.9, 99.0),
        make_location("Park B", 19.0, 99.1),
    ]

    result = validate_location(destination, candidates, attraction_name="Unknown Park",)

    assert result.status == LocationStatus.UNVERIFIED
    assert result.location is None


def test_matches_attraction_name_ignores_case_and_punctuation():
    candidate = make_location(
        "Grand Canyon Chiang Mai, Hang Dong, Thailand",
        18.7,
        98.9,
    )

    assert matches_attraction_name(
        "GRAND CANYON - CHIANG MAI",
        candidate,
    )


def test_rejects_mismatched_attraction_identity():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)
    candidate = make_location("Grand Canyon, Arizona, USA", 36.1, -112.1)

    result = validate_location(
        destination,
        [candidate],
        attraction_name="Grand Canyon Chiang Mai",
    )

    assert result.status == LocationStatus.UNVERIFIED
    assert result.location is None


def test_selects_unique_matching_candidate():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)

    candidates = [
        make_location("Grand Canyon, Arizona, USA", 36.1, -112.1),
        make_location(
            "Grand Canyon Chiang Mai, Hang Dong, Thailand",
            18.7,
            98.9,
        ),
    ]

    result = validate_location(
        destination,
        candidates,
        attraction_name="Grand Canyon Chiang Mai",
    )

    assert result.status == LocationStatus.VERIFIED
    assert result.location == candidates[1]


def test_unverified_when_multiple_names_match():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)

    candidates = [
        make_location("Elephant Nature Park, Chiang Mai", 19.2, 98.8),
        make_location("Elephant Nature Park, Another Region", 15.0, 100.0),
    ]

    result = validate_location(
        destination,
        candidates,
        attraction_name="Elephant Nature Park",
    )

    assert result.status == LocationStatus.UNVERIFIED
