from __future__ import annotations

from collections.abc import Callable
import time
from typing import TypeVar

import scripts.bootstrap_v10_cloudflare_builds as builds


_SECRET_STATE_CONVERGENCE_ATTEMPTS = 15
_SECRET_STATE_CONVERGENCE_DELAY_SECONDS = 2.0
_StateT = TypeVar("_StateT")


def script_secret_type(
    rows: list[object],
    name: str,
    *,
    invalid_code: str,
    not_unique_code: str,
    type_drift_code: str,
) -> str | None:
    """Validate a complete script-secret listing and resolve one text binding."""

    matches: list[str] = []
    for raw_row in rows:
        row = builds._object(raw_row, invalid_code)
        row_name = row.get("name")
        row_type = row.get("type")
        if (
            not isinstance(row_name, str)
            or not row_name
            or not isinstance(row_type, str)
            or not row_type
        ):
            raise builds.BootstrapStopped(invalid_code)
        if row_name == name:
            matches.append(row_type)

    if len(matches) > 1:
        raise builds.BootstrapStopped(not_unique_code)
    if not matches:
        return None
    if matches[0] != "secret_text":
        raise builds.BootstrapStopped(type_drift_code)
    return "secret_text"


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
