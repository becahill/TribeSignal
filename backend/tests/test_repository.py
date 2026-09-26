from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import Issue
from app.repository import InMemoryIssueRepository


def test_confirmations_are_atomic_and_snapshots_immutable(payload, now):
    repository = InMemoryIssueRepository()
    original = repository.add(Issue(**payload, id=uuid4(), created_at=now))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: repository.confirm(original.id), range(100)))
    assert sorted(issue.confirmation_count for issue in results) == list(range(1, 101))
    assert repository.get(original.id).confirmation_count == 100
    assert original.confirmation_count == 0
    with pytest.raises(ValidationError):
        original.confirmation_count = 99
