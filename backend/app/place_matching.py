import re
import unicodedata


def normalize_place_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return " ".join(normalized.split())


def names_match(expected: str, actual: str) -> bool:
    return normalize_place_name(expected) == normalize_place_name(actual)


OFFICE_TYPES = {
    "tour_agency",
    "travel_agency",
}


def is_likely_office(types: list[str]) -> bool:
    return bool(OFFICE_TYPES.intersection(types))


def extract_search_names(name: str) -> list[str]:
    alternatives = re.findall(r"\(([^)]+)\)", name)

    primary = re.sub(r"\([^)]*\)", "", name).strip()

    return list(dict.fromkeys(
        candidate.strip()
        for candidate in [primary, *alternatives]
        if candidate.strip()
    ))


KNOWN_PLACE_ALIASES = {
    "grand canyon chiang mai": {
        "grand canyon water park",
    },
    "sticky waterfall": {
        "buatong waterfall chet si fountain national park",
    },
    "bua thong waterfall": {
        "buatong waterfall chet si fountain national park",
    },
}


def names_match_or_alias(expected: str, actual: str) -> bool:
    """Match place names with safe normalization or approved aliases."""
    expected_name = normalize_for_matching(expected)
    actual_name = normalize_for_matching(actual)

    if expected_name == actual_name:
        return True

    # Accept a location qualifier appended in parentheses.
    actual_without_parentheses = re.sub(
        r"\s*\([^)]*\)\s*$",
        "",
        actual,
    ).strip()

    if expected_name == normalize_for_matching(actual_without_parentheses):
        return True

    return normalize_place_name(actual) in KNOWN_PLACE_ALIASES.get(
        normalize_place_name(expected),
        set(),
    )

NATURE_ACTIVITY_CATEGORIES = {
    "adventure",
    "wildlife",
}

NATURE_ACTIVITY_KEYWORDS = {
    "zipline",
    "ziplining",
    "elephant",
    "sanctuary",
    "rafting",
    "jungle",
    "atv",
}

URBAN_LOCATION_THRESHOLD_KM = 3.0


def is_suspicious_activity_location(
    name: str,
    category: str,
    distance_km: float,
) -> bool:
    """Flag potentially incorrect urban locations for outdoor activities."""
    if category not in NATURE_ACTIVITY_CATEGORIES:
        return False

    normalized_name = normalize_place_name(name)
    words = set(normalized_name.split())

    is_outdoor_activity = bool(
        words.intersection(NATURE_ACTIVITY_KEYWORDS)
    )

    return (
        is_outdoor_activity
        and distance_km < URBAN_LOCATION_THRESHOLD_KM
    )


def normalize_for_matching(name: str) -> str:
    normalized = normalize_place_name(name)

    words = normalized.split()

    if words and words[0] == "the":
        words = words[1:]

    words = [word for word in words if word != "and"]

    return " ".join(words)