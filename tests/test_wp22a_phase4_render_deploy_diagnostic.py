from __future__ import annotations

from typing import Any

import pytest

from scripts import diagnose_v10_render_deploy as diagnostic


EXPECTED_SHA = "a" * 40
NOT_BEFORE = "2026-08-22T14:27:00Z"
SERVICE_ID = "srv-da4r3d49v7es73919ntg"
DEPLOY_ID = "dep-da4r3e49v7es73919r70"
BUILD_ID = "bld-da4r3e49v7es73919r70"
SERVICE_SLUG = "omni-cio-v10-web-9x7k"


class FakeApi(diagnostic.provisioner.JsonApi):
    def __init__(
        self,
        *,
        deploy_status: str,
        reason: object,
        build_reason: object | None = None,
        include_exact_deploy: bool = True,
        deploy_created_at: str = "2026-08-22T14:27:04Z",
        duplicate_current_deploy: bool = False,
    ) -> None:
        self.deploy_status = deploy_status
        self.reason = reason
        self.build_reason = build_reason
        self.include_exact_deploy = include_exact_deploy
        self.deploy_created_at = deploy_created_at
        self.duplicate_current_deploy = duplicate_current_deploy

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
            deploys = [
                {
                    "deploy": {
                        "id": DEPLOY_ID,
                        "status": self.deploy_status,
                        "createdAt": self.deploy_created_at,
                        "commit": {"id": commit_id},
                    }
                }
            ]
            if self.duplicate_current_deploy:
                deploys.append(
                    {
                        "deploy": {
                            "id": "dep-second-current-attempt",
                            "status": self.deploy_status,
                            "createdAt": "2026-08-22T14:27:05Z",
                            "commit": {"id": EXPECTED_SHA},
                        }
                    }
                )
            return deploys
        if "/events?" in path and "type=deploy_ended" in path:
            return [
                {
                    "event": {
                        "id": "evt-da4r3e49v7es73919r70",
                        "type": "deploy_ended",
                        "timestamp": "2026-08-22T14:28:39Z",
                        "details": {
                            "deployId": DEPLOY_ID,
                            "deployStatus": "failed",
                            "status": 1,
                            "reason": self.reason,
                        },
                    }
                }
            ]
        if "/events?" in path and "type=build_ended" in path:
            if self.build_reason is None:
                return []
            return [
                {
                    "event": {
                        "id": "evt-build-da4r3e49v7es73919r70",
                        "type": "build_ended",
                        "timestamp": "2026-08-22T14:28:38Z",
                        "details": {
                            "buildId": BUILD_ID,
                            "buildStatus": "failed",
                            "status": 1,
                            "reason": self.build_reason,
                        },
                    }
                }
            ]
        raise AssertionError(path)


def _api(
    *,
    deploy_status: str,
    reason: object,
    build_reason: object | None = None,
    include_exact_deploy: bool = True,
    deploy_created_at: str = "2026-08-22T14:27:04Z",
    duplicate_current_deploy: bool = False,
) -> FakeApi:
    return FakeApi(
        deploy_status=deploy_status,
        reason=reason,
        build_reason=build_reason,
        include_exact_deploy=include_exact_deploy,
        deploy_created_at=deploy_created_at,
        duplicate_current_deploy=duplicate_current_deploy,
    )


def test_reports_build_failure_without_free_form_provider_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider_text = "sensitive-provider-message-must-not-escape"
    api = _api(
        deploy_status="build_failed",
        reason={
            "buildFailed": {"id": BUILD_ID},
            "failure": {"unhealthy": provider_text},
        },
    )
    monkeypatch.setattr(diagnostic, "_api_from_environment", lambda: api)

    assert (
        diagnostic.main(
            [
                "--expected-sha",
                EXPECTED_SHA,
                "--not-before",
                NOT_BEFORE,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "RENDER_DEPLOY_STATUS=build_failed" in output
    assert "RENDER_DEPLOY_REASON=UNHEALTHY" in output
    assert "RENDER_DEPLOY_DIAGNOSTIC=PASS" in output
    assert provider_text not in output


def test_resolves_build_failure_through_structured_build_event() -> None:
    result = diagnostic.diagnose(
        EXPECTED_SHA,
        NOT_BEFORE,
        api=_api(
            deploy_status="build_failed",
            reason={"buildFailed": {"id": BUILD_ID}},
            build_reason={"failure": {"nonZeroExit": 1}},
        ),
    )

    assert result.status == "build_failed"
    assert result.reason == "NON_ZERO_EXIT"


def test_reports_non_zero_exit_for_update_failure() -> None:
    result = diagnostic.diagnose(
        EXPECTED_SHA,
        NOT_BEFORE,
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
            NOT_BEFORE,
            api=_api(deploy_status="mystery_failed", reason={}),
        )
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_STATUS_INVALID"


def test_requires_deploy_for_exact_release() -> None:
    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(
            EXPECTED_SHA,
            NOT_BEFORE,
            api=_api(
                deploy_status="build_failed",
                reason={},
                include_exact_deploy=False,
            ),
        )
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_NOT_FOUND"


def test_rejects_stale_failed_deploy_from_earlier_attempt() -> None:
    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(
            EXPECTED_SHA,
            NOT_BEFORE,
            api=_api(
                deploy_status="build_failed",
                reason={},
                deploy_created_at="2026-08-22T14:26:59Z",
            ),
        )
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_NOT_FOUND"


def test_rejects_ambiguous_multiple_deploys_in_current_attempt() -> None:
    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(
            EXPECTED_SHA,
            NOT_BEFORE,
            api=_api(
                deploy_status="build_failed",
                reason={},
                duplicate_current_deploy=True,
            ),
        )
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_NOT_UNIQUE"


def test_rejects_non_failed_deploy() -> None:
    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(
            EXPECTED_SHA,
            NOT_BEFORE,
            api=_api(deploy_status="live", reason={}),
        )
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_DEPLOY_NOT_FAILED"


@pytest.mark.parametrize(
    "not_before",
    [
        "",
        "2026-08-22T14:27:00",
        "2026-08-22T17:27:00+03:00",
        "not-a-timestamp",
    ],
)
def test_requires_explicit_utc_attempt_boundary(not_before: str) -> None:
    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic.diagnose(
            EXPECTED_SHA,
            not_before,
            api=_api(deploy_status="build_failed", reason={}),
        )
    assert exc_info.value.code == "RENDER_DIAGNOSTIC_NOT_BEFORE_INVALID"
