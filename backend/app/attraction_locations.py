from app.geocoding import search_locations, LocationCandidate
from app.location_validation import (
    LocationStatus,
    matches_attraction_name,
    validate_location,
    normalize_name,
)
from app.schemas import AttractionRecommendation
import httpx

async def validate_attraction_locations(
    recommendations: list[AttractionRecommendation],
    destination: str,) -> list[AttractionRecommendation]:
    
    try:
        destination_candidates = await search_locations(destination, "")
    except (httpx.HTTPError, TimeoutError):
        return recommendations

    destination_location = find_destination(destination,destination_candidates,)
    
    if destination_location is None:
        return recommendations


    validated_recommendations = []

    for recommendation in recommendations:
        try:
            candidates = await search_locations(recommendation.name, destination,)
        except (httpx.HTTPError, TimeoutError):
            validated_recommendations.append(recommendation)
            continue

        result = validate_location(
            destination=destination_location,
            attraction_candidates=candidates,
            attraction_name=recommendation.name,
        )

        if result.status == LocationStatus.OUT_OF_RANGE:
            continue

        updates = {
            "location_status": result.status,
        }

        if result.location is not None:
            updates.update({
                "latitude": result.location.latitude,
                "longitude": result.location.longitude,
                "distance_km": result.distance_km,
            })

        validated_recommendations.append(
            recommendation.model_copy(update=updates)
        )

    return validated_recommendations


def find_destination(
    destination: str,
    candidates: list[LocationCandidate],
) -> LocationCandidate | None:
    expected = normalize_name(destination.split(",")[0])

    matches = [
        candidate
        for candidate in candidates
        if normalize_name(candidate.name.split(",")[0]) == expected
        or normalize_name(candidate.name.split(",")[0]) == f"{expected} city municipality"
    ]

    if len(matches) != 1:
        return None

    return matches[0]
