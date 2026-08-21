from __future__ import annotations

from datetime import datetime, timezone
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


class FakeResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def _opener(payload: object, *, status: int = 200):
    def open_request(*args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse(payload, status=status)

    return open_request


def _env(attestation: str = VALID_ATTESTATION) -> dict[str, str]:
    return {
        "RENDER_ZERO_CHARGE_ATTESTATION": attestation,
        "NEON_API_KEY": "neon-token-must-never-leak",  # pragma: allowlist secret
    }


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
        [{"id": "org-safe-preview", "plan": "free"}]
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
            {"organizations": [{"id": "org-safe-preview", "plan": "free"}]}
        ),
    )
    captured = capsys.readouterr()
    assert "PASS_FRESH_NO_PAYMENT_METHOD" in captured.out
    assert "FREE_VERIFIED" in captured.out
    assert "neon-token-must-never-leak" not in captured.out
    assert "neon-token-must-never-leak" not in captured.err
    assert "::add-mask::" not in captured.out


def test_provider_redirect_is_rejected_before_response_body_processing() -> None:
    def redirecting_opener(*args: object, **kwargs: object) -> FakeResponse:
        raise HTTPError(
            NEON_ORGANIZATIONS_URL,
            302,
            "redirect forbidden",
            hdrs=None,
            fp=None,
        )

    with pytest.raises(
        BoundaryStopped,
        match="NEON_PLAN_PREFLIGHT_REDIRECT_FORBIDDEN",
    ):
        verify_zero_cost_provider_boundary(
            env=_env(),
            now=FIXED_NOW,
            opener=redirecting_opener,
        )


def test_paid_neon_plan_stops_before_provider_mutation() -> None:
    with pytest.raises(BoundaryStopped, match="NEON_FREE_PLAN_REQUIRED"):
        verify_zero_cost_provider_boundary(
            env=_env(),
            now=FIXED_NOW,
            opener=_opener(
                {
                    "organizations": [
                        {"id": "org-paid-preview", "plan": "scale"}
                    ]
                }
            ),
        )


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
    assert "Enforce zero-charge provider boundary" in workflow
    assert (
        "RENDER_ZERO_CHARGE_ATTESTATION: "
        "${{ vars.RENDER_ZERO_CHARGE_ATTESTATION }}"
    ) in workflow
    assert "python scripts/check_v10_zero_cost_provider_boundary.py" in workflow
    assert workflow.index(
        "Verify exact-main Regression Shield before provider mutation"
    ) < workflow.index("Enforce zero-charge provider boundary")
    assert workflow.index("Enforce zero-charge provider boundary") < workflow.index(
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
