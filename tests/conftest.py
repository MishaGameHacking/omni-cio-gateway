from __future__ import annotations

from datetime import datetime, timezone
from types import ModuleType

import pytest


@pytest.fixture(autouse=True)
def refresh_final_review_orchestration_clock(request: pytest.FixtureRequest) -> None:
    """Keep process-local TTL tests independent of the calendar date of the CI run."""

    module: ModuleType | None = getattr(request, "module", None)
    if module is not None and module.__name__.endswith(
        "test_final_decision_review_orchestration_v1"
    ):
        module.NOW = datetime.now(timezone.utc)
