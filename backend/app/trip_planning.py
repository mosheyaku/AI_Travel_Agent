
from app.schemas import TravelPreferences


def build_attraction_query(preferences: TravelPreferences) -> str:
    """Build an attraction search query from travel preferences."""
    interests = ", ".join(preferences.interests)

    return (
        f"Best {interests} attractions and activities "
        f"in {preferences.destination}"
    )
