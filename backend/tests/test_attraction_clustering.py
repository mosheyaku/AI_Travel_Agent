
from app.attraction_clustering import build_attraction_clusters


def make_attraction(name, latitude, longitude, verified=True):
    return {
        "name": name,
        "location_status": "verified" if verified else "unverified",
        "latitude": latitude,
        "longitude": longitude,
        "google_place_id": name if verified else None,
    }


def test_groups_nearby_attractions():
    attractions = [
        make_attraction("Park A", 19.1767, 99.0319),
        make_attraction("Dam B", 19.1741, 99.0307),
    ]

    clusters = build_attraction_clusters(attractions)

    assert clusters == [["Park A", "Dam B"]]


def test_separates_distant_attractions():
    attractions = [
        make_attraction("Park A", 19.1767, 99.0319),
        make_attraction("Mountain B", 18.5356, 98.5221),
    ]

    clusters = build_attraction_clusters(attractions)

    assert clusters == [["Park A"], ["Mountain B"]]


def test_excludes_unverified_attractions():
    attractions = [
        make_attraction("Park A", 19.1767, 99.0319),
        make_attraction("Unknown B", None, None, verified=False),
    ]

    clusters = build_attraction_clusters(attractions)

    assert clusters == [["Park A"]]


def test_rejects_invalid_cluster_distance():
    attractions = []

    try:
        build_attraction_clusters(attractions, max_distance_km=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")
