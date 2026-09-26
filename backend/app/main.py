"""FastAPI entry point for the deterministic triage vertical slice."""

import os
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .ai import GeminiIssueAnalyzer, IssueAnalyzer, analyze_report
from .analysis_models import AnalysisRequest, AnalysisResponse, AnalysisUnavailable
from .demo_data import build_demo_issues
from .models import Issue, IssueCreate, IssueResponse
from .priority import calculate_priority
from .repository import InMemoryIssueRepository, IssueRepository


Clock = Callable[[], datetime]
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_repository(request: Request) -> IssueRepository:
    return request.app.state.repository


def get_analyzer(request: Request) -> IssueAnalyzer:
    return request.app.state.analyzer


def get_now(request: Request) -> datetime:
    now = request.app.state.clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return now.astimezone(timezone.utc)


RepositoryDependency = Annotated[IssueRepository, Depends(get_repository)]
AnalyzerDependency = Annotated[IssueAnalyzer, Depends(get_analyzer)]
NowDependency = Annotated[datetime, Depends(get_now)]


def issue_response(issue: Issue, now: datetime) -> IssueResponse:
    return IssueResponse(
        **issue.model_dump(), priority=calculate_priority(issue, now=now)
    )


def require_issue(issue: Issue | None) -> Issue:
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


def create_app(
    *,
    repository: IssueRepository | None = None,
    clock: Clock = utc_now,
    cors_origins: Sequence[str] | None = None,
    analyzer: IssueAnalyzer | None = None,
) -> FastAPI:
    app = FastAPI(
        title="TribeSignal",
        description="Transparent issue triage with deterministic, explainable priority.",
    )
    if repository is None:
        demo_mode = os.getenv("TRIBESIGNAL_DEMO_MODE", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        repository = InMemoryIssueRepository(
            initial_issues=build_demo_issues(clock()) if demo_mode else None
        )
    app.state.repository = repository
    app.state.clock = clock
    app.state.analyzer = analyzer if analyzer is not None else GeminiIssueAnalyzer()
    if cors_origins is None:
        configured_origins = os.getenv("TRIBESIGNAL_CORS_ORIGINS")
        cors_origins = (
            [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
            if configured_origins is not None
            else DEFAULT_CORS_ORIGINS
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/issues/analyze",
        response_model=AnalysisResponse,
        responses={503: {"model": AnalysisUnavailable}},
    )
    def analyze_issue(payload: AnalysisRequest, analyzer: AnalyzerDependency):
        result = analyze_report(payload.text, analyzer)
        if isinstance(result, AnalysisUnavailable):
            return JSONResponse(status_code=503, content=result.model_dump())
        return result

    @app.post("/issues", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
    def create_issue(
        payload: IssueCreate, repository: RepositoryDependency, now: NowDependency
    ) -> IssueResponse:
        issue = Issue(**payload.model_dump(), id=uuid4(), created_at=now)
        return issue_response(repository.add(issue), now)

    @app.get("/issues", response_model=list[IssueResponse])
    def list_issues(
        repository: RepositoryDependency, now: NowDependency
    ) -> list[IssueResponse]:
        return [issue_response(issue, now) for issue in repository.list()]

    @app.get("/issues/{issue_id}", response_model=IssueResponse)
    def get_issue(
        issue_id: UUID, repository: RepositoryDependency, now: NowDependency
    ) -> IssueResponse:
        return issue_response(require_issue(repository.get(issue_id)), now)

    @app.post("/issues/{issue_id}/confirm", response_model=IssueResponse)
    def confirm_issue(
        issue_id: UUID, repository: RepositoryDependency, now: NowDependency
    ) -> IssueResponse:
        return issue_response(require_issue(repository.confirm(issue_id)), now)

    return app


app = create_app()
