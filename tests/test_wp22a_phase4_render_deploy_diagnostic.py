from __future__ import annotations

from collections.abc import Callable

import pytest

from scripts import diagnose_v10_render_deploy as diagnostic


EXPECTED_SHA = "a" * 40
SERVICE_ID = "srv-da4r3d49v7es73919ntg"
DEPLOY_ID = "dep-da4r3e49v7es73919r70"


def _responses(
    *,
    deploy_status: str,
    reason: object,
    include_exact_deploy: bool = True,
) -> Callable[[str, str], object]:
    def fake_request(token: str, path: str) -> object:
        assert token == "synthetic-render-key"
        if path.startswith("/services?"):
            return [
                {
                    "service": {
                        "id": SERVICE_ID,
                        "name": diagnostic.RENDER_SERVICE_NAME,
                    }
                }
            ]
        if "/deploys?" in path:
            commit_id = EXPECTED_SHA if include_exact_deploy else "b" * 40
            return [
                {
                    "deploy": {
                        "id": DEPLOY_ID,
                        "status": deploy_status,
                        "createdAt": "2026-08-22T14:27:04Z",
                        "commit": {"id": commit_id},
                    }
                }
            ]
        if "/events?" in path:
            return [
                {
                    "event": {
                        "id": "evt-da4r3e49v7es73919r70",
                        "type": "deploy_ended",
                        "timestamp": "2026-08-22T14:28:39Z",
                        "details": {
                            "deployId": DEPLOY_ID,
                            "reason": reason,
                        },
                    }
                }
            ]
        raise AssertionError(path)

    return fake_request


def test_reports_build_failure_without_free_form_provider_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_text = "sensitive-provider-message-must-not-escape"
    monkeypatch.setenv("RENDER_API_KEY", "synthetic-render-key")
    monkeypatch.setattr(
        diagnostic,
        "_request",
        _responses(
            deploy_status="build_failed",
            reason={
                "buildFailed": {"id": "bld-da4r3e49v7es73919r70"},
                "failure": {"unhealthy": secret_text},
            },
        ),
    )

    assert diagnostic.main(["--expected-sha", EXPECTED_SHA]) == 0
    output = capsys.readouterr().out
    assert "RENDER_DEPLOY_STATUS=build_failed" in output
    assert "RENDER_DEPLOY_REASON=UNHEALTHY" in output
    assert "RENDER_DEPLOY_DIAGNOSTIC=PASS" in output
    assert secret_text not in output


def test_reports_non_zero_exit_for_update_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RENDER_API_KEY", "synthetic-render-key")
    monkeypatch.setattr(
        diagnostic,
        "_request",
        _responses(
            deploy_status="update_failed",
            reason={"failure": {"nonZeroExit": 3}},
        ),
    )

    result = diagnostic.diagnose(EXPECTED_SHA)
    assert result.service_id == SERVICE_ID
    assert result.deploy_id == DEPLOY_ID
    assert result.status == "update_failed"
    assert result.reason == "NON_ZERO_EXIT"


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ({"earlyExit": True}, "EARLY_EXIT"),
        ({"oomKilled": {"memoryLimit": "512MiB"}}, "OOM_KILLED"),
        ({"timedOutSeconds": 30}, "TIMED_OUT"),
        ({"evicted": True}, "EVICTED"),
    ],
)
def test_allowlisted_failure_reason_classification(
    failure: dict[str, object],
    expected: str,
) -> None:
    assert diagnostic._safe_failure_reason(  # noqa: SLF001 - focused parser contract
        {"reason": {"failure": failure}},
        "update_failed",
    ) == expected


def test_falls_back_to_terminal_status_when_event_is_missing() -> None:
    assert diagnostic._safe_failure_reason(  # noqa: SLF001 - focused parser contract
        {},
        "pre_deploy_failed",
    ) == "PRE_DEPLOY_FAILED"


def test_rejects_unknown_provider_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_API_KEY", "synthetic-render-key")
    monkeypatch.setattr(
        diagnostic,
        "_request",
        _responses(deploy_status="mystery_failed", reason={}),
    )

    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(EXPECTED_SHA)
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_STATUS_INVALID"


def test_requires_deploy_for_exact_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_API_KEY", "synthetic-render-key")
    monkeypatch.setattr(
        diagnostic,
        "_request",
        _responses(
            deploy_status="build_failed",
            reason={},
            include_exact_deploy=False,
        ),
    )

    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(EXPECTED_SHA)
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_NOT_FOUND"
