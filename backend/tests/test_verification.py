import json

import pytest

from app import verification
from app.schemas import AttractionRecommendation


@pytest.mark.anyio
async def test_filters_unverified_recommendations(monkeypatch):
    recommendations = [
        AttractionRecommendation(
            name="Doi Inthanon National Park",
            category="nature",
            description="Mountain hiking.",
            relevance_reason="Matches nature interests.",
            source_indices=[1],
        ),
        AttractionRecommendation(
            name="Invented Safari",
            category="wildlife",
            description="Safari with lions.",
            relevance_reason="Matches wildlife interests.",
            source_indices=[2],
        ),
    ]

    sources = [
        {
            "title": "Doi Inthanon Guide",
            "content": "Doi Inthanon National Park offers mountain hiking.",
        },
        {
            "title": "Chiang Mai Wildlife Guide",
            "content": "Information about local wildlife.",
        },
    ]

    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
            "results": [
                {
                    "id": 0,
                    "verified": True,
                    "description": "Hiking trails in Doi Inthanon National Park.",
                },
                {
                    "id": 1,
                    "verified": False,
                    "description": "",
                },
            ]
        })

    monkeypatch.setattr(verification, "generate_text", fake_generate_text)

    result = await verification.verify_recommendations(
        recommendations, sources
    )

    assert len(result) == 1
    assert result[0].name == "Doi Inthanon National Park"
    assert result[0].description == "Hiking trails in Doi Inthanon National Park."