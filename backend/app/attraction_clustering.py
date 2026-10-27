
from app.location_validation import calculate_distance_km, LocationStatus


MAX_CLUSTER_DISTANCE_KM = 40.0


def build_attraction_clusters(
    recommendations: list[dict],
    max_distance_km: float = MAX_CLUSTER_DISTANCE_KM,
) -> list[list[str]]:
    """Group verified attractions by geographic proximity."""
    if max_distance_km <= 0:
        raise ValueError("Maximum cluster distance must be positive.")

    located = [
        recommendation
        for recommendation in recommendations
        if recommendation.get("location_status") == LocationStatus.VERIFIED
        and recommendation.get("latitude") is not None
        and recommendation.get("longitude") is not None
        and recommendation.get("google_place_id")
    ]

    clusters: list[list[dict]] = []

    for attraction in located:
        best_cluster_index = None
        best_distance = float("inf")

        for index, cluster in enumerate(clusters):
            distances = [
                calculate_distance_km(
                    attraction["latitude"],
                    attraction["longitude"],
                    member["latitude"],
                    member["longitude"],
                )
                for member in cluster
            ]

            if max(distances) <= max_distance_km:
                nearest_distance = min(distances)

                if nearest_distance < best_distance:
                    best_distance = nearest_distance
                    best_cluster_index = index

        if best_cluster_index is None:
            clusters.append([attraction])
        else:
            clusters[best_cluster_index].append(attraction)

    return [
        [attraction["name"] for attraction in cluster]
        for cluster in clusters
    ]
