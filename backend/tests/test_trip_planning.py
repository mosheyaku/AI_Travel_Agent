
from app.schemas import TravelPreferences
from app.trip_planning import build_attraction_queries


def test_builds_separate_queries_for_each_interest():
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=2,
        interests=["adventure", "nature"],
    )

    queries = build_attraction_queries(preferences)

    assert queries == [
        "Best adventure attractions and activities in Chiang Mai, Thailand",
        "Best nature attractions and activities in Chiang Mai, Thailand",
    ]
