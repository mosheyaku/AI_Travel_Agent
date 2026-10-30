from app.schemas import TravelPreferences

MAX_SEARCH_DAYS = 7
ATTRACTION_CANDIDATES_PER_DAY = 6


def get_attraction_search_limit(preferences: TravelPreferences) -> int:
    """Calculate the attraction candidate limit for a trip."""
    search_days = min(preferences.duration_days, MAX_SEARCH_DAYS)
    return search_days * ATTRACTION_CANDIDATES_PER_DAY


def build_attraction_query(preferences: TravelPreferences) -> str:
    """Build an attraction search query from travel preferences."""
    interests = ", ".join(preferences.interests)

    return (
        f"Best {interests} attractions and activities "
        f"in {preferences.destination}"
    )


def build_attraction_queries(preferences: TravelPreferences) -> list[str]:
    """Build a separate attraction search query for each interest."""
    return [
        f"Best {interest} attractions and activities in {preferences.destination}"
        for interest in preferences.interests
    ]