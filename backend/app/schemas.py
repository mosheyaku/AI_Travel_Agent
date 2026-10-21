
from pydantic import BaseModel, Field


class AttractionRecommendation(BaseModel):
    name: str = Field(description="Name of the attraction")
    description: str = Field(description="Description based on the sources")
    relevance_reason: str = Field(
        description="Why this attraction matches the user's request"
    )
    source_indices: list[int] = Field(
        min_length=1,
        description="One based indices of supporting sources",
    )


class AttractionRecommendations(BaseModel):
    recommendations: list[AttractionRecommendation]
