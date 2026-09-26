from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def now():
    return datetime(2026, 9, 26, 12, tzinfo=timezone.utc)


@pytest.fixture
def payload():
    return {
        "title": "Elevator unavailable",
        "description": "The library elevator does not respond to calls.",
        "severity": "high",
        "accessibility_impact": True,
        "safety_impact": False,
        "location": "Library, first floor",
        "category": "elevator",
    }


@pytest.fixture
def client(now):
    with TestClient(create_app(clock=lambda: now)) as client:
        yield client
