import httpx
from pydantic import BaseModel, Field

from app.config import settings


GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"


class GooglePlace(BaseModel):
    place_id: str
    name: str
    latitude: float
    longitude: float
    types: list[str] = Field(default_factory=list)


async def search_google_places(
    name: str,
    destination: str,
) -> list[GooglePlace]:
    query = ", ".join(part.strip() for part in (name, destination) if part.strip())

    headers = {
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.location,places.types"
        ),
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
            types=place.get("types", []),
        )
        for place in places
    ]


class OpeningHoursPoint(BaseModel):
    day: int = Field(ge=0, le=6)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)


class OpeningHoursPeriod(BaseModel):
    open: OpeningHoursPoint
    close: OpeningHoursPoint | None = None


class PlaceOpeningHours(BaseModel):
    place_id: str
    weekday_descriptions: list[str] = Field(default_factory=list)
    periods: list[OpeningHoursPeriod] | None = None


async def get_place_opening_hours(
    place_id: str,
) -> PlaceOpeningHours:
    """Fetch regular weekly opening hours for a verified Google place."""
    if not place_id or "/" in place_id:
        raise ValueError("Invalid Google Place ID.")

    headers = {
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": (
            "id,regularOpeningHours.weekdayDescriptions," "regularOpeningHours.periods"
        ),
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://places.googleapis.com/v1/places/{place_id}",
            headers=headers,
            params={"languageCode": "en"},
        )
        response.raise_for_status()

    data = response.json()
    regular_hours = data.get("regularOpeningHours", {})

    return PlaceOpeningHours(
        place_id=data["id"],
        weekday_descriptions=regular_hours.get("weekdayDescriptions", []),
        periods=regular_hours.get("periods"),
    )


class AccommodationSuggestion(BaseModel):
    place_id: str
    name: str
    address: str
    latitude: float
    longitude: float


async def search_accommodations(
    query: str,
    destination: str,
) -> list[AccommodationSuggestion]:
    """Search Google Places for accommodation suggestions."""
    text_query = f"{query.strip()}, {destination.strip()}"

    headers = {
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.formattedAddress,"
            "places.location"
        ),
        "Content-Type": "application/json",
    }

    payload = {
        "textQuery": text_query,
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

    suggestions = []

    for place in response.json().get("places", []):
        location = place.get("location")
        name = place.get("displayName", {}).get("text")

        if not location or not name:
            continue

        suggestions.append(
            AccommodationSuggestion(
                place_id=place["id"],
                name=name,
                address=place.get("formattedAddress", ""),
                latitude=location["latitude"],
                longitude=location["longitude"],
            )
        )

    return suggestions