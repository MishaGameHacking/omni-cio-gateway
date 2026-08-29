from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from scripts.check_v10_zero_cost_provider_boundary import (
    BoundaryStopped,
    NEON_API_BASE,
    read_neon_organization,
    validate_neon_free_organization,
    validate_render_zero_charge_attestation,
    verify_zero_cost_provider_boundary,
)


FIXED_NOW = datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc)
VALID_ATTESTATION = "NO_PAYMENT_METHOD_CONFIRMED:2026-08-21T08:30:00Z"
_SAFE_ORGANIZATION_ID = "org-safe-preview"
_TEST_NEON_TOKEN = "neon-token-must-never-leak"
_ORGANIZATION_KEY = "organization"
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


def _expected_neon_url() -> str:
    return f"{NEON_API_BASE}/organizations/{_SAFE_ORGANIZATION_ID}"


def _assert_neon_request(request: Request, timeout: float) -> None:
    assert request.full_url == _expected_neon_url()
    assert request.get_method() == "GET"
    assert timeout == 30.0


def _payload(
    plan: str = "free",
    org_id: str = _SAFE_ORGANIZATION_ID,
) -> dict[str, object]:
    return {_ORGANIZATION_KEY: {"id": org_id, "plan": plan}}


def _opener(payload: object, *, status: int = 200):
    def open_request(request: Request, *, timeout: float) -> FakeResponse:
        _assert_neon_request(request, timeout)
        return FakeResponse(payload, status=status)

    return open_request


def _raw_opener(raw: bytes):
    def open_request(request: Request, *, timeout: float) -> RawResponse:
        _assert_neon_request(request, timeout)
        return RawResponse(raw)

    return open_request


def _env(attestation: str = VALID_ATTESTATION) -> dict[str, str]:
    return {
        "RENDER_ZERO_CHARGE_ATTESTATION": attestation,
        "NEON_API_KEY": _TEST_NEON_TOKEN,  # pragma: allowlist secret
        "NEON_ORG_ID": _SAFE_ORGANIZATION_ID,
    }


def _raise_http_error(status: int) -> None:
    raise HTTPError(
        _expected_neon_url(),
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


def test_exact_configured_free_neon_organization_is_required() -> None:
    organization = {"id": _SAFE_ORGANIZATION_ID, "plan": "free"}
    validate_neon_free_organization(
        organization,
        expected_org_id=_SAFE_ORGANIZATION_ID,
    )

    paid = {"id": _SAFE_ORGANIZATION_ID, "plan": "launch"}
    with pytest.raises(BoundaryStopped, match="NEON_FREE_PLAN_REQUIRED"):
        validate_neon_free_organization(
            paid,
            expected_org_id=_SAFE_ORGANIZATION_ID,
        )

    mismatch = {"id": "org-other-preview", "plan": "free"}
    with pytest.raises(BoundaryStopped, match="NEON_ORGANIZATION_ID_MISMATCH"):
        validate_neon_free_organization(
            mismatch,
            expected_org_id=_SAFE_ORGANIZATION_ID,
        )


def test_full_boundary_uses_org_scoped_endpoint_and_never_prints_token(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verify_zero_cost_provider_boundary(
        env=_env(),
        now=FIXED_NOW,
        opener=_opener(_payload()),
    )
    captured = capsys.readouterr()
    assert "PASS_FRESH_NO_PAYMENT_METHOD" in captured.out
    assert "FREE_VERIFIED" in captured.out
    assert _TEST_NEON_TOKEN not in captured.out
    assert _TEST_NEON_TOKEN not in captured.err
    assert "users/me/organizations" not in captured.out


def test_missing_or_invalid_neon_org_id_fails_before_network() -> None:
    called = False

    def opener(request: Request, *, timeout: float) -> FakeResponse:
        nonlocal called
        del request, timeout
        called = True
        return FakeResponse(_payload())

    missing = _env()
    missing.pop("NEON_ORG_ID")
    with pytest.raises(BoundaryStopped, match="NEON_ORG_ID_REQUIRED"):
        verify_zero_cost_provider_boundary(
            env=missing,
            now=FIXED_NOW,
            opener=opener,
        )

    invalid = _env()
    invalid["NEON_ORG_ID"] = "../other"
    with pytest.raises(BoundaryStopped, match="NEON_ORG_ID_INVALID"):
        verify_zero_cost_provider_boundary(
            env=invalid,
            now=FIXED_NOW,
            opener=opener,
        )

    assert called is False


def test_provider_redirect_is_rejected_before_response_body_processing() -> None:
    def redirecting_opener(request: Request, *, timeout: float) -> FakeResponse:
        _assert_neon_request(request, timeout)
        _raise_http_error(302)

    env = _env()
    with pytest.raises(
        BoundaryStopped,
        match="NEON_PLAN_PREFLIGHT_REDIRECT_FORBIDDEN",
    ):
        verify_zero_cost_provider_boundary(
            env=env,
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
    def rejecting_opener(request: Request, *, timeout: float) -> FakeResponse:
        _assert_neon_request(request, timeout)
        _raise_http_error(status)

    env = _env()
    with pytest.raises(BoundaryStopped) as stopped:
        verify_zero_cost_provider_boundary(
            env=env,
            now=FIXED_NOW,
            opener=rejecting_opener,
        )

    assert stopped.value.code == code
    assert stopped.value.status == status
    assert "provider-body-must-not-leak" not in str(stopped.value)
    assert _TEST_NEON_TOKEN not in str(stopped.value)


@pytest.mark.parametrize("transient_status", [423, 503])
def test_transient_neon_http_failure_retries_before_success(
    transient_status: int,
) -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(request: Request, *, timeout: float) -> FakeResponse:
        nonlocal attempts
        _assert_neon_request(request, timeout)
        attempts += 1
        if attempts == 1:
            _raise_http_error(transient_status)
        return FakeResponse(_payload())

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

    def opener(request: Request, *, timeout: float) -> FakeResponse:
        nonlocal attempts
        _assert_neon_request(request, timeout)
        attempts += 1
        raise TimeoutError("network unavailable")

    env = _env()
    with pytest.raises(BoundaryStopped) as stopped:
        verify_zero_cost_provider_boundary(
            env=env,
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
    opener = _raw_opener(raw)
    env = _env()

    with pytest.raises(
        BoundaryStopped,
        match="NEON_ORGANIZATION_RESPONSE_TOO_LARGE",
    ):
        verify_zero_cost_provider_boundary(
            env=env,
            now=FIXED_NOW,
            opener=opener,
        )


def test_malformed_neon_json_fails_closed_with_sanitized_error() -> None:
    opener = _raw_opener(b'{"organization":')
    env = _env()

    with pytest.raises(BoundaryStopped) as stopped:
        verify_zero_cost_provider_boundary(
            env=env,
            now=FIXED_NOW,
            opener=opener,
        )

    assert stopped.value.code == "NEON_ORGANIZATION_RESPONSE_INVALID"
    assert stopped.value.status is None
    assert _TEST_NEON_TOKEN not in str(stopped.value)


def test_direct_object_response_is_accepted_for_provider_compatibility() -> None:
    result = read_neon_organization(
        _TEST_NEON_TOKEN,
        _SAFE_ORGANIZATION_ID,
        opener=_opener({"id": _SAFE_ORGANIZATION_ID, "plan": "free"}),
    )

    assert result["id"] == _SAFE_ORGANIZATION_ID


def test_paid_neon_plan_stops_before_provider_mutation() -> None:
    opener = _opener(_payload(plan="scale"))
    env = _env()

    with pytest.raises(BoundaryStopped, match="NEON_FREE_PLAN_REQUIRED"):
        verify_zero_cost_provider_boundary(
            env=env,
            now=FIXED_NOW,
            opener=opener,
        )


def test_network_exception_handling_uses_non_redundant_oserror_boundary() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "except (URLError, TimeoutError, OSError)" not in source
    assert "except OSError:" in source


def test_user_organization_discovery_is_permanently_forbidden() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "/users/me/organizations" not in source
    assert "NEON_ORG_ID" in source


def test_phase4_workflow_is_historical_manual_only_and_fail_closed() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "v10-phase4-free-preview-deploy.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "workflow_run:" not in workflow
    assert "schedule:" not in workflow
    assert "runs-on: [self-hosted, Windows, X64, omni-cio-ci]" in workflow
    assert "LEGACY_RENDER_PHASE4_RETIRED_AMENDMENT_14" in workflow
    assert "exit /b 78" in workflow
    for forbidden in (
        "RENDER_API_KEY",
        "NEON_API_KEY",
        "RENDER_ZERO_CHARGE_ATTESTATION",
        "NEON_ORG_ID",
        "check_v10_zero_cost_provider_boundary.py",
        "provision_v10_phase4_free_preview.py",
    ):
        assert forbidden not in workflow
