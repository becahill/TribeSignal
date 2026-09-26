"""Validated issue data and the public API contract."""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
)

from .routing import RoutingDecision


class Severity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class IssueStatus(str, Enum):
    REPORTED = "reported"
    TRIAGED = "triaged"
    ROUTED = "routed"


ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)
]


class IssueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: ShortText
    description: Description
    severity: Severity
    accessibility_impact: StrictBool = False
    safety_impact: StrictBool = False
    location: ShortText
    category: ShortText


class Issue(IssueCreate):
    id: UUID
    confirmation_count: Annotated[int, Field(strict=True, ge=0)] = 0
    created_at: AwareDatetime
    status: IssueStatus = IssueStatus.REPORTED

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class PriorityComponents(BaseModel):
    severity: float
    accessibility: float
    safety: float
    confirmations: float
    aging: float


class Priority(BaseModel):
    score: Annotated[float, Field(ge=1.0, le=10.0)]
    components: PriorityComponents
    explanation: str
    calculated_at: AwareDatetime


class IssueSnapshot(BaseModel):
    """One lock-consistent view; source counts are never overwritten by aggregates."""

    model_config = ConfigDict(frozen=True)
    issue: Issue
    canonical_issue_id: UUID
    canonical_category: ShortText
    source_reports: list[Issue]
    pending_duplicate_count: int


class IssueResponse(Issue):
    priority: Priority
    routing: RoutingDecision
    canonical_issue_id: UUID
    effective_confirmation_count: Annotated[int, Field(strict=True, ge=0)]
    source_reports: list[Issue]
    pending_duplicate_count: Annotated[int, Field(strict=True, ge=0)]
