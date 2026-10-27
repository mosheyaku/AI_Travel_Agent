
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


class AttractionRecommendations(BaseModel):
    recommendations: list[AttractionRecommendation] = Field(
        max_length=15,
    )

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
    description: str
    source_indices: list[int] = Field(min_length=1)

    location_status: LocationStatus = LocationStatus.UNVERIFIED
    latitude: float | None = None
    longitude: float | None = None
    google_place_id: str | None = None

class ItineraryDay(BaseModel):
    day: int = Field(ge=1)
    activities: list[ItineraryActivity]
    max_distance_km: float | None = None

class TravelItinerary(BaseModel):
    destination: str
    days: list[ItineraryDay]
