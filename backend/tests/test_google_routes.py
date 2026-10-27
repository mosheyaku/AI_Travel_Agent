import httpx
import pytest

from app import google_routes


@pytest.mark.anyio
async def test_get_driving_route(monkeypatch):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)

        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "distanceMeters": 32500,
                        "duration": "2700s",
                    }
                ]
            },
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await google_routes.get_driving_route(
        18.6959737,
        98.8919586,
        18.906237,
        98.8971545,
    )

    assert result is not None
    assert result.distance_km == 32.5
    assert result.duration_minutes == 45


@pytest.mark.anyio
async def test_returns_none_when_no_route_exists(monkeypatch):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)

        return httpx.Response(
            200,
            json={"routes": []},
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await google_routes.get_driving_route(
        18.6959737,
        98.8919586,
        18.906237,
        98.8971545,
    )

    assert result is None