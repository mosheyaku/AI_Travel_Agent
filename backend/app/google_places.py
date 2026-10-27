
import httpx
from pydantic import BaseModel

from app.config import settings


GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"


class GooglePlace(BaseModel):
    place_id: str
    name: str
    latitude: float
    longitude: float


async def search_google_places(
    name: str,
    destination: str,
) -> list[GooglePlace]:
    query = ", ".join(
        part.strip()
        for part in (name, destination)
        if part.strip()
    )

    headers = {
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.location",
        "Content-Type": "application/json",
    }

    payload = {
        "textQuery": query,
        "languageCode": "en",
        "pageSize": 5,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            GOOGLE_PLACES_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    places = response.json().get("places", [])

    return [
        GooglePlace(
            place_id=place["id"],
            name=place["displayName"]["text"],
            latitude=place["location"]["latitude"],
            longitude=place["location"]["longitude"],
        )
        for place in places
    ]
