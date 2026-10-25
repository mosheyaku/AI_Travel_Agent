
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

    with pytest.raises(ValueError, match="no valid recommendations after retry"):
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
        match="no valid recommendations after retry",
    ):
        await recommendations.recommend_attractions("temples in Kyoto")


@pytest.mark.anyio
async def test_retries_after_invalid_source_index(monkeypatch):
    def fake_search(query: str) -> dict:
        return {
            "results": [
                {
                    "title": "Chiang Mai Travel Guide",
                    "url": "https://example.com/chiang-mai",
                    "content": "Skyline Adventure offers ziplining.",
                }
            ]
        }

    call_count = 0

    async def fake_generate_text(prompt: str) -> str:
        nonlocal call_count
        call_count += 1

        source_index = 99 if call_count == 1 else 1

        return json.dumps(
            {
                "recommendations": [
                    {
                        "name": "Skyline Adventure",
                        "category": "adventure",
                        "description": "Ziplining through the jungle.",
                        "relevance_reason": "Matches the user's interests.",
                        "source_indices": [source_index],
                    }
                ]
            }
        )

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    result = await recommendations.recommend_attractions(
        "adventure activities in Chiang Mai"
    )

    assert call_count == 2
    assert result["recommendations"][0]["name"] == "Skyline Adventure"
    assert result["recommendations"][0]["source_indices"] == [1]



@pytest.mark.anyio
async def test_keeps_valid_recommendations_when_some_are_invalid(monkeypatch):
    def fake_search(query: str) -> dict:
        return {
            "results": [
                {
                    "title": "Chiang Mai Guide",
                    "url": "https://example.com/chiang-mai",
                    "content": "Skyline Adventure offers ziplining.",
                }
            ]
        }

    async def fake_generate_text(prompt: str) -> str:
        return json.dumps(
            {
                "recommendations": [
                    {
                        "name": "Skyline Adventure",
                        "category": "adventure",
                        "description": "Ziplining through the jungle.",
                        "relevance_reason": "Matches adventure interests.",
                        "source_indices": [1],
                    },
                    {
                        "name": "Unknown Attraction",
                        "category": "adventure",
                        "description": "An unsupported attraction.",
                        "relevance_reason": "Matches adventure interests.",
                        "source_indices": [99],
                    },
                ]
            }
        )

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    async def fake_verify_recommendations(recommendations, sources):
        return recommendations
        
    monkeypatch.setattr(recommendations,"verify_recommendations",fake_verify_recommendations,)


    result = await recommendations.recommend_attractions(
        "adventure activities in Chiang Mai"
    )

    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["name"] == "Skyline Adventure"
    assert result["recommendations"][0]["source_indices"] == [1]



@pytest.mark.anyio
async def test_merges_search_results_without_duplicate_urls(monkeypatch):
    def fake_search(query: str) -> dict:
        if "adventure" in query:
            return {
                "results": [
                    {
                        "title": "Adventure Guide",
                        "url": "https://example.com/adventure",
                        "content": "Ziplining in Chiang Mai.",
                    },
                    {
                        "title": "Shared Guide",
                        "url": "https://example.com/shared",
                        "content": "Waterfalls and hiking in Chiang Mai.",
                    },
                ]
            }

        return {
            "results": [
                {
                    "title": "Shared Guide",
                    "url": "https://example.com/shared",
                    "content": "Waterfalls and hiking in Chiang Mai.",
                },
                {
                    "title": "Nature Guide",
                    "url": "https://example.com/nature",
                    "content": "Beautiful nature trails in Chiang Mai.",
                },
            ]
        }

    async def fake_generate_text(prompt: str) -> str:
        return json.dumps({
            "recommendations": [
                {
                    "name": "Chiang Mai Ziplining",
                    "category": "adventure",
                    "description": "Ziplining in Chiang Mai.",
                    "relevance_reason": "Matches adventure interests.",
                    "source_indices": [1],
                }
            ]
        })

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    async def fake_verify_recommendations(items, sources):
        return items
        
    monkeypatch.setattr(recommendations,"verify_recommendations",fake_verify_recommendations,)

    result = await recommendations.recommend_attractions([
        "Best adventure attractions in Chiang Mai",
        "Best nature attractions in Chiang Mai",
    ])

    urls = [source["url"] for source in result["sources"]]

    assert len(urls) == 3
    assert len(urls) == len(set(urls))
    assert urls == [
        "https://example.com/adventure",
        "https://example.com/shared",
        "https://example.com/nature",
    ]



@pytest.mark.anyio
async def test_combines_recommendations_from_multiple_interests(monkeypatch):
    def fake_search(query: str) -> dict:
        interest = "adventure" if "adventure" in query else "nature"

        return {
            "results": [
                {
                    "title": f"{interest} Guide",
                    "url": f"https://example.com/{interest}",
                    "content": f"Attractions for {interest} activities.",
                }
            ]
        }

    async def fake_generate_text(prompt: str) -> str:
        if "Best adventure attractions" in prompt:
            name = "Skyline Adventure"
            category = "adventure"
            source_index = 1
        else:
            name = "Doi Inthanon National Park"
            category = "nature"
            source_index = 2

        return json.dumps({
            "recommendations": [
                {
                    "name": name,
                    "category": category,
                    "description": f"An attraction for {category} activities.",
                    "relevance_reason": f"Matches {category} interests.",
                    "source_indices": [source_index],
                }
            ]
        })

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    async def fake_verify_recommendations(recommendations, sources):
        return recommendations
    
    monkeypatch.setattr(recommendations,"verify_recommendations",fake_verify_recommendations,)


    result = await recommendations.recommend_attractions([
        "Best adventure attractions in Chiang Mai",
        "Best nature attractions in Chiang Mai",
    ])

    assert len(result["recommendations"]) == 2
    assert len(result["sources"]) == 2

    assert [item["name"] for item in result["recommendations"]] == [
        "Skyline Adventure",
        "Doi Inthanon National Park",
    ]

    assert result["recommendations"][0]["source_indices"] == [1]
    assert result["recommendations"][1]["source_indices"] == [2]
