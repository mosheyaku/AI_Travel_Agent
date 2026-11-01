import json

import pytest

from app import experience_enrichment


@pytest.mark.anyio
async def test_extracts_source_supported_experience_window(monkeypatch):
    def fake_search(query):
        return {
            "results": [
                {
                    "title": "Official Schedule",
                    "url": "https://example.com/schedule",
                    "content": "The activity operates daily from 18:00 to 22:00.",
                }
            ]
        }

    async def fake_generate(prompt):
        return json.dumps(
            {
                "start_time": "18:00",
                "end_time": "22:00",
                "source_index": 1,
                "evidence": "The activity operates daily from 18:00 to 22:00.",
            }
        )

    monkeypatch.setattr(
        experience_enrichment,
        "search_attractions",
        fake_search,
    )
    monkeypatch.setattr(
        experience_enrichment,
        "generate_text",
        fake_generate,
    )

    result = await experience_enrichment.enrich_attraction_experience(
        {"name": "Example Night Activity", "activity_type": "safari"},
        "Chiang Mai",
    )

    assert result["experience_start_time"] == "18:00"
    assert result["experience_end_time"] == "22:00"


@pytest.mark.anyio
async def test_rejects_window_without_matching_source_evidence(monkeypatch):
    def fake_search(query):
        return {
            "results": [
                {
                    "title": "Visitor Information",
                    "url": "https://example.com/visit",
                    "content": "Advance booking is recommended.",
                }
            ]
        }

    async def fake_generate(prompt):
        return json.dumps(
            {
                "start_time": "18:00",
                "end_time": "22:00",
                "source_index": 1,
                "evidence": "The activity operates daily from 18:00 to 22:00.",
            }
        )

    monkeypatch.setattr(
        experience_enrichment,
        "search_attractions",
        fake_search,
    )
    monkeypatch.setattr(
        experience_enrichment,
        "generate_text",
        fake_generate,
    )

    result = await experience_enrichment.enrich_attraction_experience(
        {"name": "Example Activity"},
        "Chiang Mai",
    )

    assert result["experience_start_time"] is None
    assert result["experience_end_time"] is None