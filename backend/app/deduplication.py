
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
            dict.fromkeys(
                existing.source_indices + recommendation.source_indices
            )
        )

    return list(unique.values())