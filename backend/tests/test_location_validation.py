import pytest

from app.geocoding import LocationCandidate
from app.location_validation import (
    LocationStatus,
    calculate_distance_km,
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

    result = validate_location(destination, [attraction])

    assert result.status == LocationStatus.VERIFIED
    assert result.distance_km is not None
    assert result.distance_km < 150


def test_rejects_attraction_outside_range():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)
    attraction = make_location("Bangkok Park", 13.7563, 100.5018)

    result = validate_location(destination, [attraction])

    assert result.status == LocationStatus.OUT_OF_RANGE
    assert result.distance_km is not None
    assert result.distance_km > 150


def test_unverified_when_no_candidates():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)

    result = validate_location(destination, [])

    assert result.status == LocationStatus.UNVERIFIED
    assert result.location is None


def test_unverified_when_multiple_candidates():
    destination = make_location("Chiang Mai", 18.7883, 98.9853)

    candidates = [
        make_location("Park A", 18.9, 99.0),
        make_location("Park B", 19.0, 99.1),
    ]

    result = validate_location(destination, candidates)

    assert result.status == LocationStatus.UNVERIFIED
    assert result.location is None
