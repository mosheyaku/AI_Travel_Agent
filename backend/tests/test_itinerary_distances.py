
import pytest

from app.itinerary_distances import calculate_day_max_distance, build_attraction_distances
from app.schemas import ItineraryActivity, ItineraryDay


def test_calculates_maximum_distance():
    day = ItineraryDay(
        day=1,
        activities=[
            ItineraryActivity(
                name="Attraction A",
                activity_type="other",
                description="First attraction",
                source_indices=[1],
                latitude=18.7883,
                longitude=98.9853,
            ),
            ItineraryActivity(
                name="Attraction B",
                activity_type="other",
                description="Second attraction",
                source_indices=[2],
                latitude=18.7900,
                longitude=98.9900,
            ),
            ItineraryActivity(
                name="Attraction C",
                activity_type="other",
                description="Third attraction",
                source_indices=[3],
                latitude=19.2000,
                longitude=98.8600,
            ),
        ],
    )

    result = calculate_day_max_distance(day)

    assert result is not None
    assert result > 40


def test_returns_none_for_single_attraction():
    day = ItineraryDay(
        day=1,
        activities=[
            ItineraryActivity(
                name="Attraction A",
                activity_type="other",
                description="First attraction",
                source_indices=[1],
                latitude=18.7883,
                longitude=98.9853,
            )
        ],
    )

    assert calculate_day_max_distance(day) is None


def test_ignores_attractions_without_coordinates():
    day = ItineraryDay(
        day=1,
        activities=[
            ItineraryActivity(
                name="Attraction A",
                activity_type="other",
                description="First attraction",
                source_indices=[1],
                latitude=18.7883,
                longitude=98.9853,
            ),
            ItineraryActivity(
                name="Attraction B",
                activity_type="other",
                description="Unknown location",
                source_indices=[2],
            ),
        ],
    )

    assert calculate_day_max_distance(day) is None


def test_returns_zero_for_same_location():
    day = ItineraryDay(
        day=1,
        activities=[
            ItineraryActivity(
                name="Attraction A",
                activity_type="other",
                description="First attraction",
                source_indices=[1],
                latitude=18.7883,
                longitude=98.9853,
            ),
            ItineraryActivity(
                name="Attraction B",
                activity_type="other",
                description="Second attraction",
                source_indices=[2],
                latitude=18.7883,
                longitude=98.9853,
            ),
        ],
    )

    assert calculate_day_max_distance(day) == 0.0


def test_builds_distances_between_verified_attractions():
    recommendations = [
        {
            "name": "Attraction A",
            "latitude": 18.7883,
            "longitude": 98.9853,
            "google_place_id": "place-a",
            "location_status": "verified",
        },
        {
            "name": "Attraction B",
            "latitude": 19.2000,
            "longitude": 98.8600,
            "google_place_id": "place-b",
            "location_status": "verified",
        },
        {
            "name": "Attraction C",
            "latitude": None,
            "longitude": None,
            "google_place_id": None,
        },
    ]

    distances = build_attraction_distances(recommendations)

    assert len(distances) == 1
    assert distances[0]["from"] == "Attraction A"
    assert distances[0]["to"] == "Attraction B"
    assert distances[0]["distance_km"] > 40