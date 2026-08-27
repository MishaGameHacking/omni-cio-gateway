from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_v10_hosted_release_alignment.py"
WORKFLOW = ROOT / ".github" / "workflows" / "v10-hosted-release-alignment.yml"
EXPECTED_SHA = "a" * 40
STALE_SHA = "b" * 40


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("hosted_release_alignment", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("hosted release alignment script cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def _payload(sha: str = EXPECTED_SHA) -> dict[str, object]:
    return {
        "status": "ok",
        "release_sha": sha,
        "database": "READY",
        "synthetic_preview": True,
    }


def test_exact_release_sha_passes_without_secrets() -> None:
    module = _module()

    def opener(request: Any, *, timeout: float) -> _Response:
        assert request.full_url == f"{module.CANONICAL_PREVIEW_ORIGIN}/healthz"
        assert timeout == module._HTTP_TIMEOUT_SECONDS
        return _Response(_payload())

    module.verify_hosted_release_alignment(EXPECTED_SHA, opener=opener)


def test_stale_release_sha_fails_closed_with_sanitized_identity() -> None:
    module = _module()

    with pytest.raises(module.AlignmentStopped) as stopped:
        module.verify_hosted_release_alignment(
            EXPECTED_SHA,
            opener=lambda *_args, **_kwargs: _Response(_payload(STALE_SHA)),
        )

    assert stopped.value.code == "PREVIEW_RELEASE_SHA_DRIFT"
    assert stopped.value.expected_sha == EXPECTED_SHA
    assert stopped.value.observed_sha == STALE_SHA


def test_redirect_is_rejected_without_following_provider_location() -> None:
    module = _module()

    def opener(request: Any, *, timeout: float) -> _Response:
        del timeout
        raise HTTPError(
            request.full_url,
            302,
            "redirect",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    with pytest.raises(
        module.AlignmentStopped,
        match="PREVIEW_HEALTH_REDIRECT_FORBIDDEN",
    ):
        module.verify_hosted_release_alignment(EXPECTED_SHA, opener=opener)


def test_health_contract_must_be_ready_and_synthetic() -> None:
    module = _module()

    for patch, code in (
        ({"status": "unavailable"}, "PREVIEW_HEALTH_NOT_OK"),
        ({"database": "DEGRADED"}, "PREVIEW_DATABASE_NOT_READY"),
        ({"synthetic_preview": False}, "PREVIEW_SYNTHETIC_BOUNDARY_INVALID"),
    ):
        payload = _payload()
        payload.update(patch)
        with pytest.raises(module.AlignmentStopped, match=code):
            module.verify_hosted_release_alignment(
                EXPECTED_SHA,
                opener=lambda *_args, _payload=payload, **_kwargs: _Response(_payload),
            )


def test_release_identity_requires_full_lowercase_sha() -> None:
    module = _module()

    for value in ("short", "A" * 40, "a" * 39, "g" * 40):
        with pytest.raises(module.AlignmentStopped, match="EXPECTED_MAIN_SHA_INVALID"):
            module.verify_hosted_release_alignment(value)

    payload = _payload("not-a-sha")
    with pytest.raises(module.AlignmentStopped, match="PREVIEW_RELEASE_SHA_INVALID"):
        module.verify_hosted_release_alignment(
            EXPECTED_SHA,
            opener=lambda *_args, **_kwargs: _Response(payload),
        )


def test_transient_health_failure_is_bounded_and_retryable() -> None:
    module = _module()
    attempts = 0
    sleeps: list[float] = []

    def opener(request: Any, *, timeout: float) -> _Response:
        nonlocal attempts
        del timeout
        attempts += 1
        if attempts == 1:
            raise HTTPError(
                request.full_url,
                503,
                "warming",
                hdrs=None,
                fp=io.BytesIO(b""),
            )
        return _Response(_payload())

    module.verify_hosted_release_alignment(
        EXPECTED_SHA,
        opener=opener,
        sleep=sleeps.append,
    )

    assert attempts == 2
    assert sleeps == [module._RETRY_DELAYS_SECONDS[0]]


def test_workflow_detects_downstream_drift_even_when_deploy_failed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "name: V10 Hosted Release Alignment" in text
    assert "workflow_run:" in text
    assert "V10 Phase 4 Free Preview Deploy" in text
    assert "types:\n      - completed" in text
    assert "branches:\n      - main" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert 'cron: "23 3 * * *"' in text
    assert "github.event.workflow_run.conclusion == 'success'" not in text
    assert "runs-on: [self-hosted, Windows, X64, omni-cio-ci]" in text
    assert "cancel-in-progress: false" in text
    assert "python scripts/check_v10_exact_main_regression.py" in text
    assert "python scripts/check_v10_hosted_release_alignment.py" in text
    assert 'test "$(git rev-parse refs/remotes/origin/main)" = ' in text
    assert '"$EXPECTED_MAIN_SHA"' in text

    for secret_name in (
        "RENDER_API_KEY",
        "NEON_API_KEY",
        "RENDER_ZERO_CHARGE_ATTESTATION",
    ):
        assert secret_name not in text
