import re

from app.schemas import AttractionRecommendation


def normalize_attraction_name(name: str) -> str:
    normalized = name.casefold()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized


def deduplicate_attractions(
    recommendations: list[AttractionRecommendation],
) -> list[AttractionRecommendation]:
    unique = {}

    for recommendation in recommendations:
        name = normalize_attraction_name(recommendation.name)

        if name not in unique:
            unique[name] = recommendation.model_copy(deep=True)
            continue

        existing = unique[name]
        existing.source_indices = list(
            dict.fromkeys(existing.source_indices + recommendation.source_indices)
        )

    return list(unique.values())


def deduplicate_verified_attractions(
    recommendations: list[AttractionRecommendation],
) -> list[AttractionRecommendation]:
    """Merge verified recommendations with the same place and experience."""

    unique: list[AttractionRecommendation] = []
    seen: dict[tuple[str, str, str], AttractionRecommendation] = {}

    for recommendation in recommendations:
        if (
            recommendation.location_status != "verified"
            or not recommendation.google_place_id
        ):
            unique.append(recommendation.model_copy(deep=True))
            continue

        key = (
            recommendation.google_place_id,
            recommendation.activity_type,
            recommendation.booking_type,
        )

        if key not in seen:
            copied = recommendation.model_copy(deep=True)
            seen[key] = copied
            unique.append(copied)
            continue

        existing = seen[key]
        existing.source_indices = list(
            dict.fromkeys(existing.source_indices + recommendation.source_indices)
        )

    return unique
