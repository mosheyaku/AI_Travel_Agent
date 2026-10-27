import re
import unicodedata
from enum import StrEnum
from math import asin, cos, radians, sin, sqrt

from pydantic import BaseModel

from app.geocoding import LocationCandidate


class LocationStatus(StrEnum):
    VERIFIED = "verified"
    OUT_OF_RANGE = "out_of_range"
    UNVERIFIED = "unverified"


class LocationValidation(BaseModel):
    status: LocationStatus
    distance_km: float | None = None
    location: LocationCandidate | None = None


def calculate_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius_km = 6371.0

    lat1, lon1, lat2, lon2 = map(
        radians, (lat1, lon1, lat2, lon2)
    )

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )

    return 2 * radius_km * asin(min(1.0, sqrt(a)))


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = normalized.casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return " ".join(normalized.split())


def matches_attraction_name(
    attraction_name: str,
    candidate: LocationCandidate,
) -> bool:
    expected = normalize_name(attraction_name)
    actual = normalize_name(candidate.name.split(",")[0])

    return bool(expected) and expected == actual



def validate_location(
    destination: LocationCandidate,
    attraction_candidates: list[LocationCandidate],
    attraction_name: str,
    max_distance_km: float = 150,
) -> LocationValidation:
    matching_candidates = [
        candidate
        for candidate in attraction_candidates
        if matches_attraction_name(attraction_name, candidate)
    ]

    if len(matching_candidates) != 1:
        return LocationValidation(status=LocationStatus.UNVERIFIED)

    attraction = matching_candidates[0]

    distance = calculate_distance_km(
        destination.latitude,
        destination.longitude,
        attraction.latitude,
        attraction.longitude,
    )

    status = (
        LocationStatus.VERIFIED
        if distance <= max_distance_km
        else LocationStatus.OUT_OF_RANGE
    )

    return LocationValidation(
        status=status,
        distance_km=round(distance, 1),
        location=attraction,
    )
