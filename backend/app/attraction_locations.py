from app.geocoding import search_locations, LocationCandidate
from app.location_validation import (
    LocationStatus,
    matches_attraction_name,
    validate_location,
    normalize_name,
)
from app.schemas import AttractionRecommendation
import httpx

from app.google_places import search_google_places
from app.place_matching import names_match
from app.location_validation import calculate_distance_km

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
            places = await search_google_places(
                recommendation.name,
                destination,
            )
        except (httpx.HTTPError, TimeoutError):
            validated_recommendations.append(recommendation)
            continue

        matching_places = [
            place for place in places
            if names_match(recommendation.name, place.name)
        ]

        if len(matching_places) != 1:
            validated_recommendations.append(recommendation)
            continue

        place = matching_places[0]

        distance = calculate_distance_km(
            destination_location.latitude,
            destination_location.longitude,
            place.latitude,
            place.longitude,
        )

        if distance > 150:
            continue

        validated_recommendations.append(
            recommendation.model_copy(
                update={
                    "location_status": LocationStatus.VERIFIED,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "distance_km": round(distance, 1),
                }
            )
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
