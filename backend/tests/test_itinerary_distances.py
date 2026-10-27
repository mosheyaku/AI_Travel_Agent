import pytest

from app.itinerary_distances import calculate_day_max_distance
from app.schemas import ItineraryActivity, ItineraryDay


def test_calculates_maximum_distance():
    day = ItineraryDay(
        day=1,
        activities=[
            ItineraryActivity(
                name="Attraction A",
                description="First attraction",
                source_indices=[1],
                latitude=18.7883,
                longitude=98.9853,
            ),
            ItineraryActivity(
                name="Attraction B",
                description="Second attraction",
                source_indices=[2],
                latitude=18.7900,
                longitude=98.9900,
            ),
            ItineraryActivity(
                name="Attraction C",
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
                description="First attraction",
                source_indices=[1],
                latitude=18.7883,
                longitude=98.9853,
            ),
            ItineraryActivity(
                name="Attraction B",
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
                description="First attraction",
                source_indices=[1],
                latitude=18.7883,
                longitude=98.9853,
            ),
            ItineraryActivity(
                name="Attraction B",
                description="Second attraction",
                source_indices=[2],
                latitude=18.7883,
                longitude=98.9853,
            ),
        ],
    )

    assert calculate_day_max_distance(day) == 0.0
