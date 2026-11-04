import json

from app.schemas import AttractionRecommendation
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
                        "activity_type": "zipline",
                        "description": "Ziplining through the jungle.",
                        "relevance_reason": "Matches the user's interests.",
                        "source_indices": [source_index],
                    }
                ]
            }
        )

    async def fake_verify_recommendations(items, sources, destination=None):
        return items

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)
    monkeypatch.setattr(
        recommendations,
        "verify_recommendations",
        fake_verify_recommendations,
    )

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
                        "activity_type": "zipline",
                        "description": "Ziplining through the jungle.",
                        "relevance_reason": "Matches adventure interests.",
                        "source_indices": [1],
                    },
                    {
                        "name": "Unknown Attraction",
                        "category": "adventure",
                        "activity_type": "other",
                        "description": "An unsupported attraction.",
                        "relevance_reason": "Matches adventure interests.",
                        "source_indices": [99],
                    },
                ]
            }
        )

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    async def fake_verify_recommendations(items, sources, destination):
        return items

    monkeypatch.setattr(
        recommendations,
        "verify_recommendations",
        fake_verify_recommendations,
    )

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
        return json.dumps(
            {
                "recommendations": [
                    {
                        "name": "Chiang Mai Ziplining",
                        "category": "adventure",
                        "activity_type": "zipline",
                        "description": "Ziplining in Chiang Mai.",
                        "relevance_reason": "Matches adventure interests.",
                        "source_indices": [1],
                    }
                ]
            }
        )

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    async def fake_verify_recommendations(items, sources, destination):
        return items

    monkeypatch.setattr(
        recommendations,
        "verify_recommendations",
        fake_verify_recommendations,
    )

    result = await recommendations.recommend_attractions(
        [
            "Best adventure attractions in Chiang Mai",
            "Best nature attractions in Chiang Mai",
        ]
    )

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

        return json.dumps(
            {
                "recommendations": [
                    {
                        "name": name,
                        "category": category,
                        "activity_type": (
                            "zipline" if category == "adventure" else "hiking"
                        ),
                        "description": f"An attraction for {category} activities.",
                        "relevance_reason": f"Matches {category} interests.",
                        "source_indices": [source_index],
                    }
                ]
            }
        )

    monkeypatch.setattr(recommendations, "search_attractions", fake_search)
    monkeypatch.setattr(recommendations, "generate_text", fake_generate_text)

    async def fake_verify_recommendations(items, sources, destination):
        return items

    monkeypatch.setattr(
        recommendations,
        "verify_recommendations",
        fake_verify_recommendations,
    )

    result = await recommendations.recommend_attractions(
        [
            "Best adventure attractions in Chiang Mai",
            "Best nature attractions in Chiang Mai",
        ]
    )

    assert len(result["recommendations"]) == 2
    assert len(result["sources"]) == 2

    assert [item["name"] for item in result["recommendations"]] == [
        "Skyline Adventure",
        "Doi Inthanon National Park",
    ]

    assert result["recommendations"][0]["source_indices"] == [1]
    assert result["recommendations"][1]["source_indices"] == [2]


def test_merge_recommendations_preserves_source_indices():
    existing = {
        "sources": [
            {
                "title": "Adventure Guide",
                "url": "https://example.com/adventure",
            }
        ],
        "recommendations": [
            {
                "name": "Skyline Adventure",
                "google_place_id": "place_1",
                "source_indices": [1],
            }
        ],
    }

    additional = {
        "sources": [
            {
                "title": "Waterfall Guide",
                "url": "https://example.com/waterfall",
            }
        ],
        "recommendations": [
            {
                "name": "Sticky Waterfall",
                "google_place_id": "place_2",
                "source_indices": [1],
            }
        ],
    }

    result = recommendations.merge_recommendation_results(
        existing,
        additional,
    )

    assert len(result["sources"]) == 2
    assert len(result["recommendations"]) == 2

    assert result["recommendations"][0]["source_indices"] == [1]
    assert result["recommendations"][1]["source_indices"] == [2]

    assert additional["recommendations"][0]["source_indices"] == [1]


def test_merge_recommendations_deduplicates_google_places():
    existing = {
        "sources": [
            {
                "title": "First Guide",
                "url": "https://example.com/first",
            }
        ],
        "recommendations": [
            {
                "name": "Skyline Adventure",
                "google_place_id": "same_place",
                "source_indices": [1],
            }
        ],
    }

    additional = {
        "sources": [
            {
                "title": "Second Guide",
                "url": "https://example.com/second",
            }
        ],
        "recommendations": [
            {
                "name": "Skyline Zipline Experience",
                "google_place_id": "same_place",
                "source_indices": [1],
            }
        ],
    }

    result = recommendations.merge_recommendation_results(
        existing,
        additional,
    )

    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["name"] == "Skyline Adventure"


def test_merge_recommendations_reuses_existing_source():
    existing = {
        "sources": [
            {
                "title": "Chiang Mai Guide",
                "url": "https://example.com/guide",
            }
        ],
        "recommendations": [],
    }

    additional = {
        "sources": [
            {
                "title": "Chiang Mai Guide",
                "url": "https://example.com/guide",
            }
        ],
        "recommendations": [
            {
                "name": "Sticky Waterfall",
                "google_place_id": "waterfall_1",
                "source_indices": [1],
            }
        ],
    }

    result = recommendations.merge_recommendation_results(
        existing,
        additional,
    )

    assert len(result["sources"]) == 1
    assert result["recommendations"][0]["source_indices"] == [1]


def test_merge_recommendations_preserves_duplicate_sources():
    existing = {
        "sources": [
            {
                "title": "Guide One",
                "url": "https://example.com/one",
            }
        ],
        "recommendations": [
            {
                "name": "Skyline Adventure",
                "google_place_id": "place_1",
                "source_indices": [1],
            }
        ],
    }

    additional = {
        "sources": [
            {
                "title": "Guide Two",
                "url": "https://example.com/two",
            }
        ],
        "recommendations": [
            {
                "name": "Skyline Zipline",
                "google_place_id": "place_1",
                "source_indices": [1],
            }
        ],
    }

    result = recommendations.merge_recommendation_results(
        existing,
        additional,
    )

    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["source_indices"] == [1, 2]
    assert len(result["sources"]) == 2

    assert existing["recommendations"][0]["source_indices"] == [1]


def test_merge_recommendations_rejects_invalid_source_references():
    existing = {
        "sources": [],
        "recommendations": [],
    }

    additional = {
        "sources": [
            {
                "title": "Guide",
                "url": "https://example.com/guide",
            }
        ],
        "recommendations": [
            {
                "name": "Invalid Attraction",
                "google_place_id": "place_1",
                "source_indices": [99],
            }
        ],
    }

    result = recommendations.merge_recommendation_results(
        existing,
        additional,
    )

    assert result["recommendations"] == []


@pytest.mark.parametrize(
    ("max_attractions", "query_count", "expected"),
    [
        (18, 2, 18),
        (18, 4, 9),
        (18, 6, 6),
        (18, 8, 5),
        (5, 1, 10),
    ],
)
def test_candidate_limit_expands_search_pool(
    max_attractions,
    query_count,
    expected,
):
    assert (
        recommendations.get_per_query_candidate_limit(
            max_attractions,
            query_count,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("max_attractions", "query_count"),
    [
        (0, 2),
        (-1, 2),
        (10, 0),
    ],
)
def test_candidate_limit_rejects_invalid_inputs(
    max_attractions,
    query_count,
):
    with pytest.raises(ValueError):
        recommendations.get_per_query_candidate_limit(
            max_attractions,
            query_count,
        )


def test_select_diverse_attractions_balances_categories():
    items = [
        AttractionRecommendation(
            name=f"Nature {index}",
            category="nature",
            activity_type="hiking",
            description="Nature attraction",
            relevance_reason="Nature experience",
            source_indices=[1],
        )
        for index in range(4)
    ]

    items += [
        AttractionRecommendation(
            name=f"Adventure {index}",
            category="adventure",
            activity_type="zipline",
            description="Adventure attraction",
            relevance_reason="Adventure experience",
            source_indices=[1],
        )
        for index in range(3)
    ]

    selected = recommendations.select_diverse_attractions(items, 4)

    assert [item.name for item in selected] == [
        "Nature 0",
        "Adventure 0",
        "Nature 1",
        "Adventure 1",
    ]


def test_select_diverse_attractions_does_not_mutate_input():
    items = [
        AttractionRecommendation(
            name=f"Attraction {index}",
            category="nature",
            activity_type="hiking",
            description="Nature attraction",
            relevance_reason="Nature experience",
            source_indices=[1],
        )
        for index in range(3)
    ]

    original_names = [item.name for item in items]

    recommendations.select_diverse_attractions(items, 2)

    assert [item.name for item in items] == original_names
