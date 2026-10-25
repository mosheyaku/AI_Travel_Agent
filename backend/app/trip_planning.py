
from app.schemas import TravelPreferences


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