import json
from unittest.mock import AsyncMock

import pytest

from app import verification
from app.schemas import AttractionRecommendation


@pytest.mark.anyio
async def test_filters_unverified_recommendations(monkeypatch):
    recommendations = [
        AttractionRecommendation(
            name="Doi Inthanon National Park",
            category="nature",
            activity_type="hiking",
            description="A national park with hiking trails.",
            relevance_reason="Matches nature interests.",
            source_indices=[1],
        ),
        AttractionRecommendation(
            name="Unknown Attraction",
            category="adventure",
            activity_type="other",
            description="An unsupported attraction.",
            relevance_reason="Matches adventure interests.",
            source_indices=[2],
        ),
    ]

    sources = [
        {
            "title": "Doi Inthanon Guide",
            "content": "Doi Inthanon National Park has hiking trails.",
        },
        {
            "title": "Adventure Guide",
            "content": "General adventure activities in Chiang Mai.",
        },
    ]

    async def fake_generate_text(prompt: str) -> str:
        if prompt.lstrip().startswith("Identify which sources"):
            if "Attraction: Doi Inthanon National Park" in prompt:
                return json.dumps({"source_indices": [1]})

            return json.dumps({"source_indices": []})

        return json.dumps({
            "verified": True,
            "description": "Hiking trails in Doi Inthanon National Park.",
            "activity_type": "hiking",
            "duration_type": "unknown",
        })

    monkeypatch.setattr(
        verification,
        "generate_text",
        fake_generate_text,
    )

    result = await verification.verify_recommendations(
        recommendations,
        sources,
        destination="Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].name == "Doi Inthanon National Park"
    assert result[0].description == (
        "Hiking trails in Doi Inthanon National Park."
    )
    assert result[0].activity_type == "hiking"
    assert result[0].duration_type == "unknown"
    assert result[0].source_indices == [1]


@pytest.mark.anyio
async def test_verification_removes_unsupported_activity(monkeypatch):
    recommendation = AttractionRecommendation(
        name="Sri Lanna National Park",
        category="nature",
        activity_type="rafting",
        description="A national park offering waterfalls and white-water rafting.",
        relevance_reason="Matches nature interests.",
        source_indices=[1],
    )

    sources = [
        {
            "title": "Sri Lanna National Park",
            "content": "The park features waterfalls, hiking trails, and a reservoir.",
        }
    ]

    mock_generate = AsyncMock(
        side_effect=[
            json.dumps({"source_indices": [1]}),
            json.dumps({
                "verified": True,
                "description": (
                    "A national park featuring waterfalls, "
                    "hiking trails, and a reservoir."
                ),
                "activity_type": "hiking",
                "duration_type": "unknown",
            }),
        ]
    )

    monkeypatch.setattr(
        verification,
        "generate_text",
        mock_generate,
    )

    result = await verification.verify_recommendations(
        [recommendation],
        sources,
        destination="Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert "white-water rafting" not in result[0].description
    assert "waterfalls" in result[0].description
    assert result[0].activity_type == "hiking"
    assert result[0].duration_type == "unknown"
    assert result[0].source_indices == [1]
    assert mock_generate.await_count == 2


@pytest.mark.anyio
async def test_excludes_sources_about_unnamed_attractions(monkeypatch):
    recommendation = AttractionRecommendation(
        name="Elephant Nature Park",
        category="wildlife",
        activity_type="elephant_sanctuary",
        description=(
            "An elephant sanctuary offering river rafting "
            "and elephant painting."
        ),
        relevance_reason="Matches wildlife interests.",
        source_indices=[1, 2],
    )

    sources = [
        {
            "title": "Elephant Adventures in Chiang Mai",
            "content": (
                "An unnamed elephant sanctuary offers "
                "river rafting and elephant painting."
            ),
        },
        {
            "title": "Elephant Nature Park Guide",
            "content": (
                "Elephant Nature Park is an elephant rescue "
                "and rehabilitation center."
            ),
        },
    ]

    mock_generate = AsyncMock(
        side_effect=[
            json.dumps({"source_indices": [2]}),
            json.dumps({
                "verified": True,
                "description": (
                    "Elephant Nature Park is an elephant "
                    "rescue and rehabilitation center."
                ),
                "activity_type": "elephant_sanctuary",
                "duration_type": "unknown",
            }),
        ]
    )

    monkeypatch.setattr(
        verification,
        "generate_text",
        mock_generate,
    )

    result = await verification.verify_recommendations(
        [recommendation],
        sources,
        destination="Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].source_indices == [2]
    assert result[0].activity_type == "elephant_sanctuary"
    assert "rafting" not in result[0].description
    assert "painting" not in result[0].description

    verification_prompt = mock_generate.await_args_list[1].args[0]

    assert '"index": 2' in verification_prompt
    assert '"index": 1' not in verification_prompt
    assert mock_generate.await_count == 2


@pytest.mark.anyio
async def test_rejects_generic_attraction_collection(monkeypatch):
    recommendation = AttractionRecommendation(
        name="Zoo Attractions Chiang Mai",
        category="wildlife",
        activity_type="zoo",
        description="A collection of zoos and animal parks.",
        relevance_reason="Matches wildlife interests.",
        source_indices=[1],
    )

    sources = [
        {
            "title": "Zoo Attractions Chiang Mai",
            "content": (
                "Explore different zoos and wildlife parks "
                "in Chiang Mai."
            ),
        }
    ]

    mock_generate = AsyncMock(
        return_value=json.dumps({"source_indices": []})
    )

    monkeypatch.setattr(
        verification,
        "generate_text",
        mock_generate,
    )

    result = await verification.verify_recommendations(
        [recommendation],
        sources,
        destination="Chiang Mai, Thailand",
    )

    assert result == []
    assert mock_generate.await_count == 1


@pytest.mark.anyio
async def test_verification_corrects_unsupported_duration(monkeypatch):
    recommendation = AttractionRecommendation(
        name="Example Waterfall",
        category="nature",
        activity_type="waterfall",
        description="A waterfall visit.",
        relevance_reason="Matches nature interests.",
        source_indices=[1],
        duration_type="full_day",
    )

    sources = [
        {
            "title": "Example Waterfall",
            "content": "Example Waterfall is accessible via a walking trail.",
        }
    ]

    mock_generate = AsyncMock(
        side_effect=[
            json.dumps({"source_indices": [1]}),
            json.dumps({
                "verified": True,
                "description": "A waterfall accessible via a walking trail.",
                "activity_type": "waterfall",
                "duration_type": "unknown",
            }),
        ]
    )

    monkeypatch.setattr(
        verification,
        "generate_text",
        mock_generate,
    )

    result = await verification.verify_recommendations(
        [recommendation],
        sources,
        destination="Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].duration_type == "unknown"
    assert result[0].activity_type == "waterfall"


@pytest.mark.anyio
async def test_rejects_invalid_verified_activity_type(monkeypatch):
    recommendation = AttractionRecommendation(
        name="Example Adventure Park",
        category="adventure",
        activity_type="zipline",
        description="An adventure park.",
        relevance_reason="Matches adventure interests.",
        source_indices=[1],
    )

    sources = [
        {
            "title": "Example Adventure Park",
            "content": "Example Adventure Park offers zipline activities.",
        }
    ]

    mock_generate = AsyncMock(
        side_effect=[
            json.dumps({"source_indices": [1]}),
            json.dumps({
                "verified": True,
                "description": "An adventure park offering zipline activities.",
                "activity_type": "Zipline Experience",
                "duration_type": "unknown",
            }),
        ]
    )

    monkeypatch.setattr(
        verification,
        "generate_text",
        mock_generate,
    )

    with pytest.raises(ValueError, match="Invalid verified activity type"):
        await verification.verify_recommendations(
            [recommendation],
            sources,
            destination="Chiang Mai, Thailand",
        )