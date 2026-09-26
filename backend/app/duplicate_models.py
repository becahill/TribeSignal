"""Review evidence, kept separate from report intake and priority inputs."""

import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StringConstraints,
    field_validator, model_validator,
)

from .models import Issue, IssueResponse


class DuplicateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


# Fail closed if generated prose strays into consequential judgments. This is an
# additional conservative guard, not an instruction-injection detector. Prose is
# never parsed as commands or used by the priority engine.
PROHIBITED_REASON = re.compile(
    r"\b(priorit\w*|severit\w*|urgen\w*|rank(?:s|ed|ing|ings)?|rout(?:e|es|ed|ing)|slas?|escalat\w*|"
    r"operational|action\w*|dispatch\w*|deadline\w*|merge\w*|consolidat\w*)\b",
    re.IGNORECASE,
)


class DuplicateAssessment(DuplicateModel):
    is_possible_duplicate: StrictBool
    confidence: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator("reason")
    @classmethod
    def evidence_only(cls, value: str) -> str:
        if PROHIBITED_REASON.search(value):
            raise ValueError("Only semantic comparison evidence is allowed")
        return value


class DuplicateSuggestion(DuplicateModel):
    id: UUID
    issue_id: UUID
    candidate_issue_id: UUID
    confidence: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    status: Literal["pending", "confirmed", "rejected"] = "pending"
    origin: Literal["gemini", "demo_fixture"] = "gemini"
    created_at: AwareDatetime
    reviewed_at: AwareDatetime | None = None
    reviewed_by: Literal["human"] | None = None
    canonical_issue_id: UUID | None = None

    @model_validator(mode="after")
    def coherent_review(self):
        if self.issue_id == self.candidate_issue_id:
            raise ValueError("A suggestion must compare two different reports")
        if self.status == "pending":
            if self.reviewed_at or self.reviewed_by or self.canonical_issue_id:
                raise ValueError("Pending suggestions cannot have a review")
        elif self.reviewed_at is None or self.reviewed_by != "human":
            raise ValueError("A decision must record a human review")
        if (self.status == "confirmed") != (self.canonical_issue_id is not None):
            raise ValueError("Only confirmed suggestions have a canonical issue")
        return self


class DuplicateSuggestionResponse(DuplicateSuggestion):
    issue: Issue
    candidate: Issue


class DuplicateAnalysisResponse(DuplicateModel):
    status: Literal["complete", "unavailable"]
    suggestions: list[DuplicateSuggestionResponse]
    remaining_candidates: Annotated[int, Field(ge=0)]


class DuplicateReviewResponse(DuplicateModel):
    suggestion: DuplicateSuggestionResponse
    issues: list[IssueResponse]


class DuplicateReviewRequest(DuplicateModel):
    """No client-controlled decision metadata or aggregation inputs."""
