
from app.deduplication import deduplicate_attractions
from app.schemas import AttractionRecommendation


def test_removes_duplicate_attractions_with_different_names():
    recommendations = [
        AttractionRecommendation(
            name="Skyline Adventure",
            category="adventure",
            description="Zipline experience.",
            relevance_reason="Matches adventure interests.",
            source_indices=[1],
        ),
        AttractionRecommendation(
            name="SKYLINE-ADVENTURE",
            category="adventure",
            description="Zipline experience.",
            relevance_reason="Matches adventure interests.",
            source_indices=[2],
        ),
        AttractionRecommendation(
            name="Doi Inthanon National Park",
            category="nature",
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
            description="Elephant sanctuary.",
            relevance_reason="Matches wildlife interests.",
            source_indices=[1],
        ),
        AttractionRecommendation(
            name="Elephant Nature",
            category="wildlife",
            description="A different attraction.",
            relevance_reason="Matches wildlife interests.",
            source_indices=[2],
        ),
    ]

    result = deduplicate_attractions(recommendations)

    assert len(result) == 2