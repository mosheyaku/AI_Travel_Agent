
import json

import pytest

from app import recommendations


@pytest.mark.anyio
async def test_returns_empty_recommendations_when_search_has_no_results(
    monkeypatch,
):
    def fake_search(query: str) -> dict:
        return {"results": []}

    async def fail_if_called(prompt: str) -> str:
        pytest.fail("The LLM should not be called when search returns no results.")

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fail_if_called)

    result = await recommendations.recommend_attractions("temples in Kyoto")

    assert result["recommendations"] == []
    assert result["sources"] == []


@pytest.mark.anyio
async def test_rejects_nonexistent_source_index(monkeypatch):
    def fake_search(query: str) -> dict:
        return {
            "results": [
                {
                    "title": "Kyoto Travel Guide",
                    "url": "https://example.com/kyoto",
                    "content": "A guide to temples in Kyoto.",
                }
            ]
        }

    async def fake_generate_text(prompt: str) -> str:
        return json.dumps(
            {
                "recommendations": [
                    {
                        "name": "Kiyomizudera Temple",
                        "category": "culture",
                        "description": "A historical temple in Kyoto.",
                        "relevance_reason": "Matches the request.",
                        "source_indices": [99],
                    }
                ]
            }
        )

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    with pytest.raises(ValueError, match="source index"):
        await recommendations.recommend_attractions("temples in Kyoto")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "model_response",
    [
        "This is not valid JSON",
        json.dumps(
            {
                "recommendations": [
                    {
                        "name": "Kyoto Temple",
                        "category": "temples",
                        "description": "A historical temple.",
                        "relevance_reason": "Matches the request.",
                        "source_indices": [1],
                    }
                ]
            }
        ),
    ],
)
async def test_rejects_invalid_model_response(monkeypatch, model_response):
    def fake_search(query: str) -> dict:
        return {
            "results": [
                {
                    "title": "Kyoto Travel Guide",
                    "url": "https://example.com/kyoto",
                    "content": "A guide to temples in Kyoto.",
                }
            ]
        }

    async def fake_generate_text(prompt: str) -> str:
        return model_response

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    with pytest.raises(
        ValueError,
        match="invalid recommendation response",
    ):
        await recommendations.recommend_attractions("temples in Kyoto")
