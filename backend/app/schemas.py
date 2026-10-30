
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from app.location_validation import LocationStatus

AttractionCategory = Literal[
    "adventure",
    "nature",
    "culture",
    "food",
    "wildlife",
    "relaxation",
    "other",
]


class AttractionRecommendation(BaseModel):
    name: str = Field(description="Name of the attraction")
    category: AttractionCategory
    activity_type: str = Field(
    min_length=1,
    description="Specific activity type in lowercase snake_case",)
    description: str = Field(description="Description based on the sources")
    relevance_reason: str = Field(
        description="Why this attraction matches the user's request"
    )
    source_indices: list[int] = Field(
        min_length=1,
        description="One based indices of supporting sources",
    )

    location_status: LocationStatus = LocationStatus.UNVERIFIED
    latitude: float | None = None
    longitude: float | None = None
    distance_km: float | None = None
    google_place_id: str | None = None
    duration_type: Literal["short", "half_day", "full_day", "unknown"] = "unknown"


class AttractionRecommendations(BaseModel):
    recommendations: list[AttractionRecommendation]
    
    @model_validator(mode="after")
    def validate_unique_names(self):
        names = [
            recommendation.name.strip().casefold()
            for recommendation in self.recommendations
        ]

        if len(names) != len(set(names)):
            raise ValueError("Duplicate attraction names are not allowed.")

        return self


class TravelPreferences(BaseModel):
    destination: str = Field(min_length=2)
    duration_days: int = Field(ge=1, le=30)
    budget: float | None = Field(default=None, gt=0)
    interests: list[AttractionCategory] = Field(min_length=1)
    pace: Literal["relaxed", "balanced", "active"] = "balanced"


class ItineraryActivity(BaseModel):
    name: str = Field(min_length=1)
    activity_type: str = Field(min_length=1)
    description: str
    source_indices: list[int] = Field(min_length=1)

    location_status: LocationStatus = LocationStatus.UNVERIFIED
    latitude: float | None = None
    longitude: float | None = None
    google_place_id: str | None = None
    duration_type: Literal[
        "short", "half_day", "full_day", "unknown"
    ] = "unknown"

    # Estimated schedule, calculated after itinerary generation.
    start_time: str | None = None
    end_time: str | None = None
    estimated_duration_minutes: int | None = None
    travel_minutes_from_previous: int | None = None

class ItineraryDay(BaseModel):
    day: int = Field(ge=1)
    activities: list[ItineraryActivity]
    max_distance_km: float | None = None

    # Driving between consecutive attractions only.
    driving_distance_km: float | None = None
    driving_duration_minutes: int | None = None
    driving_status: Literal[
        "verified", "exceeds_limit", "unknown"
    ] = "unknown"

    # Round-trip driving from the destination city center.
    total_driving_distance_km: float | None = None
    total_driving_duration_minutes: int | None = None
    

class TravelItinerary(BaseModel):
    destination: str
    days: list[ItineraryDay]
