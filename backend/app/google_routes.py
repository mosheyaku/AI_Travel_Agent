import math
from dataclasses import dataclass

import httpx

from app.config import settings


ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


@dataclass(frozen=True)
class DrivingRoute:
    distance_km: float
    duration_minutes: float


async def get_driving_route(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> DrivingRoute | None:
    """Get driving distance and estimated duration from Google Routes."""

    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": origin_latitude,
                    "longitude": origin_longitude,
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": destination_latitude,
                    "longitude": destination_longitude,
                }
            }
        },
        "travelMode": "DRIVE",
    }

    headers = {
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            ROUTES_API_URL,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

    routes = response.json().get("routes", [])

    if not routes:
        return None

    route = routes[0]

    distance_meters = route["distanceMeters"]
    duration_seconds = float(route["duration"].removesuffix("s"))

    return DrivingRoute(
        distance_km=round(distance_meters / 1000, 1),
        duration_minutes=math.ceil(duration_seconds / 60),
    )