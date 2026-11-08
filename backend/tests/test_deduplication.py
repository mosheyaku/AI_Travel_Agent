from app.deduplication import (
    deduplicate_attractions,
    deduplicate_verified_attractions,
)
from app.location_validation import LocationStatus
from app.schemas import AttractionRecommendation


def test_removes_duplicate_attractions_with_different_names():
    recommendations = [
        AttractionRecommendation(
            name="Skyline Adventure",
            category="adventure",
            activity_type="zipline",
            description="Zipline experience.",
            relevance_reason="Matches adventure interests.",
            source_indices=[1],
        ),
        AttractionRecommendation(
            name="SKYLINE-ADVENTURE",
            category="adventure",
            activity_type="zipline",
            description="Zipline experience.",
            relevance_reason="Matches adventure interests.",
            source_indices=[2],
        ),
        AttractionRecommendation(
            name="Doi Inthanon National Park",
            category="nature",
            activity_type="hiking",
            description="Mountain hiking.",
            relevance_reason="Matches nature interests.",
            source_indices=[3],
        ),
    ]

    result = deduplicate_attractions(recommendations)

    assert len(result) == 2
    assert result[0].name == "Skyline Adventure"
    assert result[1].name == "Doi Inthanon National Park"
    assert result[0].source_indices == [1, 2]


def test_keeps_different_attractions():
    recommendations = [
        AttractionRecommendation(
            name="Elephant Nature Park",
            category="wildlife",
            activity_type="elephant_sanctuary",
            description="Elephant sanctuary.",
            relevance_reason="Matches wildlife interests.",
            source_indices=[1],
        ),
        AttractionRecommendation(
            name="Elephant Nature",
            category="wildlife",
            activity_type="other",
            description="A different attraction.",
            relevance_reason="Matches wildlife interests.",
            source_indices=[2],
        ),
    ]

    result = deduplicate_attractions(recommendations)

    assert len(result) == 2


def make_verified_attraction(
    name: str,
    source_index: int,
    place_id: str = "place-123",
    activity_type: str = "zipline",
    booking_type: str = "scheduled_activity",
) -> AttractionRecommendation:
    return AttractionRecommendation(
        name=name,
        category="adventure",
        activity_type=activity_type,
        description=f"Experience at {name}.",
        relevance_reason="Matches adventure interests.",
        source_indices=[source_index],
        location_status=LocationStatus.VERIFIED,
        latitude=18.7883,
        longitude=98.9853,
        google_place_id=place_id,
        booking_type=booking_type,
    )


def test_merges_verified_duplicate_experiences():
    recommendations = [
        make_verified_attraction("Kingkong Smile Zipline", 1),
        make_verified_attraction("Chiang Mai Kingkong Smile Zipline", 2),
    ]

    result = deduplicate_verified_attractions(recommendations)

    assert len(result) == 1
    assert result[0].name == "Kingkong Smile Zipline"
    assert result[0].source_indices == [1, 2]


def test_keeps_different_experiences_at_same_place():
    recommendations = [
        make_verified_attraction(
            "ATV Adventure",
            1,
            activity_type="atv",
        ),
        make_verified_attraction(
            "Zipline Adventure",
            2,
            activity_type="zipline",
        ),
    ]

    result = deduplicate_verified_attractions(recommendations)

    assert len(result) == 2


def test_keeps_different_booking_types_at_same_place():
    recommendations = [
        make_verified_attraction(
            "Guided Nature Tour",
            1,
            activity_type="hiking",
            booking_type="guided_tour",
        ),
        make_verified_attraction(
            "Self-Guided Nature Walk",
            2,
            activity_type="hiking",
            booking_type="self_guided",
        ),
    ]

    result = deduplicate_verified_attractions(recommendations)

    assert len(result) == 2


def test_keeps_unverified_attractions():
    recommendations = [
        make_verified_attraction("Zipline A", 1),
        make_verified_attraction("Zipline B", 2),
    ]

    for recommendation in recommendations:
        recommendation.location_status = LocationStatus.UNVERIFIED

    result = deduplicate_verified_attractions(recommendations)

    assert len(result) == 2


def test_deduplication_does_not_mutate_original_recommendations():
    recommendations = [
        make_verified_attraction("Kingkong Smile Zipline", 1),
        make_verified_attraction("Chiang Mai Kingkong Smile Zipline", 2),
    ]

    result = deduplicate_verified_attractions(recommendations)

    assert result[0].source_indices == [1, 2]
    assert recommendations[0].source_indices == [1]
    assert recommendations[1].source_indices == [2]
