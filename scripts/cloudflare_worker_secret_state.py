from __future__ import annotations

from collections.abc import Callable
import time
from typing import TypeVar


_SECRET_STATE_CONVERGENCE_ATTEMPTS = 15
_SECRET_STATE_CONVERGENCE_DELAY_SECONDS = 2.0
_StateT = TypeVar("_StateT")


def wait_for_secret_state(
    read_state: Callable[[], _StateT],
    expected_state: _StateT,
    *,
    attempts: int = _SECRET_STATE_CONVERGENCE_ATTEMPTS,
    delay_seconds: float = _SECRET_STATE_CONVERGENCE_DELAY_SECONDS,
) -> bool:
    """Wait only on read-after-mutation visibility; never repeat the mutation."""

    if attempts < 1:
        raise ValueError("secret-state convergence attempts must be positive")
    if delay_seconds < 0:
        raise ValueError("secret-state convergence delay must be non-negative")

    for attempt in range(1, attempts + 1):
        if read_state() == expected_state:
            return True
        if attempt < attempts:
            time.sleep(delay_seconds)
    return False
