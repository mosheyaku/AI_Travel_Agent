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
        (
            "Specific named places and operators for "
            "zipline rafting ATV climbing outdoor adventure "
            "in Chiang Mai, Thailand"
        ),
        "Best nature attractions and activities in Chiang Mai, Thailand",
        (
            "Specific named places and operators for "
            "waterfalls caves hiking national parks scenic trails "
            "in Chiang Mai, Thailand"
        ),
    ]


def test_build_attraction_queries_covers_each_interest():
    preferences = TravelPreferences(
        destination="Chiang Mai, Thailand",
        duration_days=3,
        interests=["adventure", "nature", "wildlife"],
    )

    queries = build_attraction_queries(preferences)

    assert len(queries) == 6
    assert len(set(queries)) == 6

    assert all("Chiang Mai, Thailand" in query for query in queries)

    assert any("zipline" in query for query in queries)
    assert any("waterfalls" in query for query in queries)
    assert any("wildlife" in query for query in queries)


def test_build_attraction_queries_avoids_duplicate_interests():
    preferences = TravelPreferences(
        destination="Phuket, Thailand",
        duration_days=3,
        interests=["adventure", "adventure"],
    )

    queries = build_attraction_queries(preferences)

    assert len(queries) == 2
