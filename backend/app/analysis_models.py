"""Proposal-only contract, deliberately independent of IssueCreate and priority."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints

from .models import Description, ShortText


class AnalysisModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )


class AnalysisRequest(AnalysisModel):
    text: Description


class AnalysisCategory(str, Enum):
    ELEVATOR = "Elevator"
    ELECTRICAL = "Electrical"
    PLUMBING = "Plumbing"
    WALKWAY = "Walkway"
    LIGHTING = "Lighting"
    NETWORK = "Network"
    OTHER = "Other"


class AnalysisProposal(AnalysisModel):
    title: ShortText
    description: Description
    # Unknown locations stay blank; the reporter must supply one before creation.
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
    category: AnalysisCategory
    accessibility_impact: StrictBool
    safety_impact: StrictBool


class AnalysisReview(AnalysisModel):
    status: Literal["review"] = "review"
    proposal: AnalysisProposal


class AnalysisEmergency(AnalysisModel):
    status: Literal["emergency"] = "emergency"
    message: str


class AnalysisUnavailable(AnalysisModel):
    status: Literal["unavailable"] = "unavailable"
    message: str = "AI assistance is unavailable. You can enter the report details manually."


AnalysisResponse = Annotated[
    AnalysisReview | AnalysisEmergency | AnalysisUnavailable,
    Field(discriminator="status"),
]
