from __future__ import annotations

from typing import Any

import pytest

from scripts import diagnose_v10_render_deploy as diagnostic


EXPECTED_SHA = "a" * 40
SERVICE_ID = "srv-da4r3d49v7es73919ntg"
DEPLOY_ID = "dep-da4r3e49v7es73919r70"
SERVICE_SLUG = "omni-cio-v10-web-9x7k"


class FakeApi(diagnostic.provisioner.JsonApi):
    def __init__(
        self,
        *,
        deploy_status: str,
        reason: object,
        include_exact_deploy: bool = True,
    ) -> None:
        self.deploy_status = deploy_status
        self.reason = reason
        self.include_exact_deploy = include_exact_deploy

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        assert method == "GET"
        assert body is None
        assert expected == frozenset({200})
        assert timeout == 30.0
        if path == "/owners?limit=100":
            return [{"owner": {"id": "tea-free-preview"}}]
        if path.startswith("/services?"):
            assert "ownerId=tea-free-preview" in path
            assert "name=omni-cio-v10-web" in path
            return [
                {
                    "service": {
                        "id": SERVICE_ID,
                        "slug": SERVICE_SLUG,
                        "autoDeploy": "no",
                        "name": diagnostic.provisioner.RENDER_SERVICE_NAME,
                        "type": "web_service",
                        "repo": diagnostic.provisioner.REPOSITORY_URL,
                        "branch": "main",
                        "serviceDetails": {
                            "runtime": "python",
                            "plan": "free",
                            "region": diagnostic.provisioner.RENDER_REGION,
                            "healthCheckPath": "/healthz",
                            "url": f"https://{SERVICE_SLUG}.onrender.com",
                            "envSpecificDetails": {
                                "buildCommand": diagnostic.provisioner.BUILD_COMMAND,
                                "startCommand": diagnostic.provisioner.START_COMMAND,
                            },
                        },
                    }
                }
            ]
        if "/deploys?" in path:
            commit_id = EXPECTED_SHA if self.include_exact_deploy else "b" * 40
            return [
                {
                    "deploy": {
                        "id": DEPLOY_ID,
                        "status": self.deploy_status,
                        "createdAt": "2026-08-22T14:27:04Z",
                        "commit": {"id": commit_id},
                    }
                }
            ]
        if "/events?" in path:
            assert "type=deploy_ended" in path
            return [
                {
                    "event": {
                        "id": "evt-da4r3e49v7es73919r70",
                        "type": "deploy_ended",
                        "timestamp": "2026-08-22T14:28:39Z",
                        "details": {
                            "deployId": DEPLOY_ID,
                            "reason": self.reason,
                        },
                    }
                }
            ]
        raise AssertionError(path)


def _api(
    *,
    deploy_status: str,
    reason: object,
    include_exact_deploy: bool = True,
) -> FakeApi:
    return FakeApi(
        deploy_status=deploy_status,
        reason=reason,
        include_exact_deploy=include_exact_deploy,
    )


def test_reports_build_failure_without_free_form_provider_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_text = "sensitive-provider-message-must-not-escape"
    api = _api(
        deploy_status="build_failed",
        reason={
            "buildFailed": {"id": "bld-da4r3e49v7es73919r70"},
            "failure": {"unhealthy": secret_text},
        },
    )
    monkeypatch.setattr(diagnostic, "_api_from_environment", lambda: api)

    assert diagnostic.main(["--expected-sha", EXPECTED_SHA]) == 0
    output = capsys.readouterr().out
    assert "RENDER_DEPLOY_STATUS=build_failed" in output
    assert "RENDER_DEPLOY_REASON=UNHEALTHY" in output
    assert "RENDER_DEPLOY_DIAGNOSTIC=PASS" in output
    assert secret_text not in output


def test_reports_non_zero_exit_for_update_failure() -> None:
    result = diagnostic.diagnose(
        EXPECTED_SHA,
        api=_api(
            deploy_status="update_failed",
            reason={"failure": {"nonZeroExit": 3}},
        ),
    )

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
    assert diagnostic._safe_failure_reason(  # noqa: SLF001 - parser contract
        {"reason": {"failure": failure}},
        "update_failed",
    ) == expected


def test_falls_back_to_terminal_status_when_event_is_missing() -> None:
    assert diagnostic._safe_failure_reason(  # noqa: SLF001 - parser contract
        {},
        "pre_deploy_failed",
    ) == "PRE_DEPLOY_FAILED"


def test_rejects_unknown_provider_status() -> None:
    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(
            EXPECTED_SHA,
            api=_api(deploy_status="mystery_failed", reason={}),
        )
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_STATUS_INVALID"


def test_requires_deploy_for_exact_release() -> None:
    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(
            EXPECTED_SHA,
            api=_api(
                deploy_status="build_failed",
                reason={},
                include_exact_deploy=False,
            ),
        )
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_NOT_FOUND"
