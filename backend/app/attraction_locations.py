import httpx

from app.geocoding import LocationCandidate, search_locations
from app.google_places import search_google_places
from app.location_validation import (
    LocationStatus,
    calculate_distance_km,
    normalize_name,
)
from app.place_matching import (
    extract_search_names,
    is_likely_office,
    names_match,
)
from app.schemas import AttractionRecommendation


async def validate_attraction_locations(
    recommendations: list[AttractionRecommendation],
    destination: str,
) -> list[AttractionRecommendation]:
    try:
        destination_candidates = await search_locations(destination, "")
    except (httpx.HTTPError, TimeoutError):
        return recommendations

    destination_location = find_destination(
        destination,
        destination_candidates,
    )

    if destination_location is None:
        return recommendations

    validated_recommendations = []

    for recommendation in recommendations:
        search_names = extract_search_names(recommendation.name)
        matching_places = []

        for search_name in search_names[:2]:
            try:
                places = await search_google_places(
                    search_name,
                    destination,
                )
            except (httpx.HTTPError, TimeoutError):
                continue

            matching_places = [
                place
                for place in places
                if names_match(search_name, place.name)
                and not is_likely_office(place.types)
            ]

            if matching_places:
                break

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
