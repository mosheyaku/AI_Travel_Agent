import re
import unicodedata


def normalize_place_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return " ".join(normalized.split())


def names_match(expected: str, actual: str) -> bool:
    return normalize_place_name(expected) == normalize_place_name(actual)