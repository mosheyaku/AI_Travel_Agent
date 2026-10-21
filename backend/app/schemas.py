
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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


class AttractionRecommendations(BaseModel):
    recommendations: list[AttractionRecommendation] = Field(
        max_length=5,
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