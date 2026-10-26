import asyncio
import time

import httpx
from pydantic import BaseModel


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AITravelArchitect/0.1 (contact: mosheyaku.dev@gmail.com)"

_request_lock = asyncio.Lock()
_last_request = 0.0
_cache: dict[str, list["LocationCandidate"]] = {}


class LocationCandidate(BaseModel):
    name: str
    latitude: float
    longitude: float
    osm_type: str
    osm_id: int


async def search_locations(
    name: str,
    destination: str,
) -> list[LocationCandidate]:
    global _last_request

    query = f"{name.strip()}, {destination.strip()}"

    async with _request_lock:
        if query in _cache:
            return list(_cache[query])

        elapsed = time.monotonic() - _last_request
        if elapsed < 1:
            await asyncio.sleep(1 - elapsed)

        _last_request = time.monotonic()

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 5,
                },
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()

        candidates = [
            LocationCandidate(
                name=item["display_name"],
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
                osm_type=item["osm_type"],
                osm_id=int(item["osm_id"]),
            )
            for item in response.json()
        ]

        _cache[query] = candidates
        return list(candidates)
