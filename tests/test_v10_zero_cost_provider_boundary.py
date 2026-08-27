from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts.check_v10_zero_cost_provider_boundary import (
    BoundaryStopped,
    NEON_ORGANIZATIONS_URL,
    validate_neon_free_organization,
    validate_render_zero_charge_attestation,
    verify_zero_cost_provider_boundary,
)


FIXED_NOW = datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc)
VALID_ATTESTATION = "NO_PAYMENT_METHOD_CONFIRMED:2026-08-21T08:30:00Z"
_SAFE_ORGANIZATION_ID = "org-safe-preview"
_TEST_NEON_TOKEN = "neon-token-must-never-leak"
_BOUNDARY_STEP = "Enforce zero-charge provider boundary"
_ORGANIZATIONS_KEY = "organizations"
SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_v10_zero_cost_provider_boundary.py"
)


class FakeResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            return self._raw
        return self._raw[:amount]


class RawResponse(FakeResponse):
    def __init__(self, raw: bytes, status: int = 200) -> None:
        self.status = status
        self._raw = raw


def _opener(payload: object, *, status: int = 200):
    def open_request(*args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse(payload, status=status)

    return open_request


def _env(attestation: str = VALID_ATTESTATION) -> dict[str, str]:
    return {
        "RENDER_ZERO_CHARGE_ATTESTATION": attestation,
        "NEON_API_KEY": _TEST_NEON_TOKEN,  # pragma: allowlist secret
    }


def _http_error(status: int) -> HTTPError:
    return HTTPError(
        NEON_ORGANIZATIONS_URL,
        status,
        "provider response must stay sanitized",
        hdrs=None,
        fp=io.BytesIO(b"provider-body-must-not-leak"),
    )


def test_fresh_render_attestation_is_accepted() -> None:
    validate_render_zero_charge_attestation(
        VALID_ATTESTATION,
        now=FIXED_NOW,
    )


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("", "RENDER_ZERO_CHARGE_ATTESTATION_INVALID"),
        (
            "NO_PAYMENT_METHOD_CONFIRMED:2026-08-20T08:59:59Z",
            "RENDER_ZERO_CHARGE_ATTESTATION_STALE",
        ),
        (
            "NO_PAYMENT_METHOD_CONFIRMED:2026-08-21T09:05:01Z",
            "RENDER_ZERO_CHARGE_ATTESTATION_FROM_FUTURE",
        ),
        (
            "PAYMENT_METHOD_UNKNOWN:2026-08-21T08:30:00Z",
            "RENDER_ZERO_CHARGE_ATTESTATION_INVALID",
        ),
    ],
)
def test_invalid_stale_or_future_render_attestation_is_rejected(
    value: str,
    code: str,
) -> None:
    with pytest.raises(BoundaryStopped, match=code):
        validate_render_zero_charge_attestation(value, now=FIXED_NOW)


def test_exactly_one_free_neon_organization_is_required() -> None:
    validate_neon_free_organization(
        [{"id": _SAFE_ORGANIZATION_ID, "plan": "free"}]
    )

    with pytest.raises(BoundaryStopped, match="NEON_FREE_PLAN_REQUIRED"):
        validate_neon_free_organization(
            [{"id": "org-paid-preview", "plan": "launch"}]
        )

    with pytest.raises(BoundaryStopped, match="NEON_ORGANIZATION_NOT_UNIQUE"):
        validate_neon_free_organization(
            [
                {"id": "org-one", "plan": "free"},
                {"id": "org-two", "plan": "free"},
            ]
        )


def test_full_boundary_verification_is_read_only_and_never_prints_token(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verify_zero_cost_provider_boundary(
        env=_env(),
        now=FIXED_NOW,
        opener=_opener(
            {_ORGANIZATIONS_KEY: [{"id": _SAFE_ORGANIZATION_ID, "plan": "free"}]}
        ),
    )
    captured = capsys.readouterr()
    assert "PASS_FRESH_NO_PAYMENT_METHOD" in captured.out
    assert "FREE_VERIFIED" in captured.out
    assert _TEST_NEON_TOKEN not in captured.out
    assert _TEST_NEON_TOKEN not in captured.err
    assert "::add-mask::" not in captured.out


def test_provider_redirect_is_rejected_before_response_body_processing() -> None:
    def redirecting_opener(*args: object, **kwargs: object) -> FakeResponse:
        raise _http_error(302)

    with pytest.raises(
        BoundaryStopped,
        match="NEON_PLAN_PREFLIGHT_REDIRECT_FORBIDDEN",
    ):
        verify_zero_cost_provider_boundary(
            env=_env(),
            now=FIXED_NOW,
            opener=redirecting_opener,
        )


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "NEON_API_KEY_INVALID"),
        (403, "NEON_API_KEY_INSUFFICIENT"),
    ],
)
def test_neon_auth_failure_distinguishes_invalid_from_insufficient_scope(
    status: int,
    code: str,
) -> None:
    def rejecting_opener(*args: object, **kwargs: object) -> FakeResponse:
        raise _http_error(status)

    with pytest.raises(BoundaryStopped) as stopped:
        verify_zero_cost_provider_boundary(
            env=_env(),
            now=FIXED_NOW,
            opener=rejecting_opener,
        )

    assert stopped.value.code == code
    assert stopped.value.status == status
    assert "provider-body-must-not-leak" not in str(stopped.value)
    assert _TEST_NEON_TOKEN not in str(stopped.value)


def test_transient_neon_http_failure_retries_before_success() -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(*args: object, **kwargs: object) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _http_error(503)
        return FakeResponse(
            {_ORGANIZATIONS_KEY: [{"id": _SAFE_ORGANIZATION_ID, "plan": "free"}]}
        )

    verify_zero_cost_provider_boundary(
        env=_env(),
        now=FIXED_NOW,
        opener=opener,
        sleeper=sleeps.append,
    )

    assert attempts == 2
    assert sleeps == [1.0]


def test_exhausted_network_retries_fail_closed_without_secret_leak() -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(*args: object, **kwargs: object) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        raise TimeoutError("network unavailable")

    with pytest.raises(BoundaryStopped) as stopped:
        verify_zero_cost_provider_boundary(
            env=_env(),
            now=FIXED_NOW,
            opener=opener,
            sleeper=sleeps.append,
        )

    assert stopped.value.code == "NEON_PLAN_PREFLIGHT_NETWORK_ERROR"
    assert attempts == 3
    assert sleeps == [1.0, 2.0]
    assert _TEST_NEON_TOKEN not in str(stopped.value)


def test_oversized_neon_response_fails_closed_before_json_processing() -> None:
    raw = b"{" + (b"x" * 1_048_576) + b"}"

    with pytest.raises(
        BoundaryStopped,
        match="NEON_ORGANIZATIONS_RESPONSE_TOO_LARGE",
    ):
        verify_zero_cost_provider_boundary(
            env=_env(),
            now=FIXED_NOW,
            opener=lambda *_args, **_kwargs: RawResponse(raw),
        )


def test_paid_neon_plan_stops_before_provider_mutation() -> None:
    with pytest.raises(BoundaryStopped, match="NEON_FREE_PLAN_REQUIRED"):
        verify_zero_cost_provider_boundary(
            env=_env(),
            now=FIXED_NOW,
            opener=_opener(
                {
                    _ORGANIZATIONS_KEY: [
                        {"id": "org-paid-preview", "plan": "scale"}
                    ]
                }
            ),
        )


def test_network_exception_handling_uses_non_redundant_oserror_boundary() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "except (URLError, TimeoutError, OSError)" not in source
    assert "except OSError:" in source


def test_deployment_workflow_requires_fresh_attestation_and_test_toolchain() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "v10-phase4-free-preview-deploy.yml"
    ).read_text(encoding="utf-8")

    assert "Verify exact-main Regression Shield before provider mutation" in workflow
    assert "python scripts/check_v10_exact_main_regression.py" in workflow
    assert "tests/test_v10_exact_main_regression.py" in workflow
    assert _BOUNDARY_STEP in workflow
    assert (
        "RENDER_ZERO_CHARGE_ATTESTATION: "
        "${{ vars.RENDER_ZERO_CHARGE_ATTESTATION }}"
    ) in workflow
    assert "python scripts/check_v10_zero_cost_provider_boundary.py" in workflow
    assert workflow.index(
        "Verify exact-main Regression Shield before provider mutation"
    ) < workflow.index(_BOUNDARY_STEP)
    assert workflow.index(_BOUNDARY_STEP) < workflow.index(
        "Provision and deploy zero-cost synthetic preview"
    )
    assert "tests/test_v10_zero_cost_provider_boundary.py" in workflow
    assert "scripts/windows_ci_lock.py project" in workflow
    assert "requirements-dev.txt windows-requirements-dev.txt" in workflow
    assert "--require-hashes -r windows-requirements-dev.txt" in workflow
    assert "import fastapi, psycopg, pytest" in workflow
    assert "\npermissions:\n" not in workflow
    assert (
        "  deploy-free-preview:\n"
        "    name: Deploy exact accepted main to Render and Neon free preview\n"
        "    permissions:\n"
        "      actions: read\n"
        "      contents: read\n"
    ) in workflow
