import httpx
import pytest

from app import google_places


@pytest.mark.anyio
async def test_search_google_places_returns_locations(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def post(self, url, headers, json):
            assert url == google_places.GOOGLE_PLACES_URL
            assert json["textQuery"] == "Pongyang Adventure Park, Chiang Mai, Thailand"
            assert headers["X-Goog-FieldMask"] == ("places.id,places.displayName,places.location,places.types")

            return httpx.Response(
                200,
                json={
                    "places": [
                        {
                            "id": "test-place-id",
                            "displayName": {
                                "text": "Pong Yang Jungle Coaster & Zipline"
                            },
                            
                            "location": {
                                "latitude": 18.9168336,
                                "longitude": 98.821529,
                            },
                            
                            "types": [
                                "tourist_attraction",
                                "point_of_interest",
                            ],
                        }
                    ]
                },
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        google_places.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(),
    )

    result = await google_places.search_google_places(
        "Pongyang Adventure Park",
        "Chiang Mai, Thailand",
    )

    assert len(result) == 1
    assert result[0].place_id == "test-place-id"
    assert result[0].name == "Pong Yang Jungle Coaster & Zipline"
    assert result[0].latitude == 18.9168336
    assert result[0].longitude == 98.821529
    assert result[0].types == ["tourist_attraction","point_of_interest",]


@pytest.mark.anyio
async def test_search_google_places_returns_empty_list(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def post(self, url, headers, json):
            return httpx.Response(
                200,
                json={},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        google_places.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(),
    )

    result = await google_places.search_google_places(
        "Unknown Attraction",
        "Chiang Mai, Thailand",
    )

    assert result == []
