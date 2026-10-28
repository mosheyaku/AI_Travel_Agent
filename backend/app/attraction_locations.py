import httpx

from app.geocoding import LocationCandidate, search_locations
from app.google_places import search_google_places
from app.llm_place_matching import match_place_with_llm
from app.location_validation import (
    LocationStatus,
    calculate_distance_km,
    normalize_name,
)
from app.place_matching import (
    extract_search_names,
    is_likely_office,
    is_suspicious_activity_location,
    names_match_or_alias,
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
        all_places_by_id = {}

        for search_name in search_names:
            try:
                places = await search_google_places(
                    search_name,
                    destination,
                )
            except (httpx.HTTPError, TimeoutError):
                continue

            for place in places:
                if is_likely_office(place.types):
                    continue

                all_places_by_id[place.place_id] = place

        all_places = list(all_places_by_id.values())

        matching_places = [
            place
            for place in all_places
            if any(
                names_match_or_alias(candidate_name, place.name)
                for candidate_name in search_names
            )
        ]

        if len(matching_places) == 1:
            place = matching_places[0]
        elif all_places:
            place = await match_place_with_llm(
                recommendation.name,
                destination,
                all_places,
            )
        else:
            place = None

        if place is None:
            validated_recommendations.append(recommendation)
            continue

        distance = calculate_distance_km(
            destination_location.latitude,
            destination_location.longitude,
            place.latitude,
            place.longitude,
        )

        if distance > 150:
            continue

        if is_suspicious_activity_location(
            recommendation.name,
            recommendation.category,
            distance,
        ):
            validated_recommendations.append(recommendation)
            continue

        validated_recommendations.append(
            recommendation.model_copy(
                update={
                    "location_status": LocationStatus.VERIFIED,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "distance_km": round(distance, 1),
                    "google_place_id": place.place_id,
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
        or normalize_name(candidate.name.split(",")[0]) == (
            f"{expected} city municipality"
        )
    ]

    if len(matches) != 1:
        return None

    return matches[0]
