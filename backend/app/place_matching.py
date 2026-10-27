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