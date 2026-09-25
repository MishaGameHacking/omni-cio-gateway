from __future__ import annotations

import json
from urllib.request import Request

import pytest

from scripts import timeweb_app_release as release


EXPECTED_SHA = "a" * 40
LKG_SHA = "b" * 40
CANDIDATE_HOST = "omni-cio-v10-app.example.invalid"


class _Response:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self, amount: int = -1) -> bytes:
        return self._raw if amount < 0 else self._raw[:amount]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        del args


class _Opener:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = list(responses)
        self.requests: list[Request] = []

    def open(self, request: Request, *, timeout: float) -> _Response:
        del timeout
        self.requests.append(request)
        return self.responses.pop(0)


class _Livez:
    def __init__(self, sha: str = EXPECTED_SHA) -> None:
        self.sha = sha

    def open(self, request: Request, *, timeout: float) -> _Response:
        del request, timeout
        return _Response({"status": "ok", "release_sha": self.sha})


def _app(*, active_sha: str = LKG_SHA, status: str = "active") -> dict[str, object]:
    return {
        "id": 17,
        "type": "backend",
        "name": release.CANONICAL_APP_NAME,
        "status": status,
        "framework": "docker",
        "branch_name": "main",
        "is_auto_deploy": False,
        "commit_sha": active_sha,
        "repository": {"full_name": release.CANONICAL_REPOSITORY},
        "domains": [{"fqdn": CANDIDATE_HOST}],
        "envs": {
            "OMNI_V10_HOSTED_RUNTIME": "1",
            "OMNI_V10_PUBLIC_HOSTNAME": "omnicio.ru",
            "OMNI_V10_CANDIDATE_HOSTNAME": CANDIDATE_HOST,
            "OMNI_V10_RELEASE_SHA": EXPECTED_SHA,
            "OMNI_V10_POSTGRES_RUNTIME_ROLE": "omni_cio_hosted_api",
            "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED": "true",
            "PUBLIC_MULTI_USER_ENABLED": "false",
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "false",
            "OMNI_V10_POSTGRES_DSN": "postgresql://opaque",
        },
    }


class _Api:
    def __init__(self, app: dict[str, object]) -> None:
        self.app_payload = app
        self.rows = [{"id": "deploy-lkg", "commit_sha": LKG_SHA, "status": "success"}]
        self.calls: list[tuple[str, str]] = []
        self.sleeper = lambda _seconds: None

    def list_apps(self) -> dict[str, object]:
        return {"apps": [self.app_payload], "meta": {"total": 1}}

    def get_app(self, app_id: str) -> dict[str, object]:
        assert app_id == "17"
        return {"app": self.app_payload}

    def list_deploys(self, app_id: str) -> dict[str, object]:
        assert app_id == "17"
        return {"deploys": self.rows, "meta": {"total": len(self.rows)}}

    def deploy_once(self, app_id: str, sha: str) -> dict[str, object]:
        self.calls.append((app_id, sha))
        row = {"id": "deploy-new", "commit_sha": sha, "status": "success"}
        self.rows.insert(0, row)
        self.app_payload["commit_sha"] = sha
        self.app_payload["status"] = "active"
        return {"deploy": row}


def test_observe_requires_current_main_sha() -> None:
    api = _Api(_app(active_sha=EXPECTED_SHA))
    livez = _Livez()
    with pytest.raises(
        release.ReleaseStopped, match="TIMEWEB_APP_RELEASE_MAIN_SHA_DRIFT"
    ):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=LKG_SHA,
            token="token",
            api=api,
            livez_opener=livez,
        )


def test_observe_accepts_exact_active_sha_and_livez() -> None:
    last_known_good = release.run(
        operation="observe",
        expected_sha=EXPECTED_SHA,
        observed_main_sha=EXPECTED_SHA,
        token="token",
        api=_Api(_app(active_sha=EXPECTED_SHA)),
        livez_opener=_Livez(),
    )
    assert last_known_good == LKG_SHA


def test_observe_rejects_release_sha_drift() -> None:
    api = _Api(_app(active_sha=EXPECTED_SHA))
    livez = _Livez(LKG_SHA)
    with pytest.raises(
        release.ReleaseStopped, match="TIMEWEB_APP_RELEASE_LIVEZ_SHA_DRIFT"
    ):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            api=api,
            livez_opener=livez,
        )


def test_candidate_rejects_autodeploy_and_public_activation() -> None:
    autodeploy = _app(active_sha=EXPECTED_SHA)
    autodeploy["is_auto_deploy"] = True
    autodeploy_api = _Api(autodeploy)
    livez = _Livez()
    with pytest.raises(
        release.ReleaseStopped, match="TIMEWEB_APP_RELEASE_AUTODEPLOY_FORBIDDEN"
    ):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            api=autodeploy_api,
            livez_opener=livez,
        )

    activated = _app(active_sha=EXPECTED_SHA)
    assert isinstance(activated["envs"], dict)
    activated["envs"]["PUBLIC_MULTI_USER_ENABLED"] = "true"
    activated_api = _Api(activated)
    with pytest.raises(release.ReleaseStopped, match="TIMEWEB_APP_RELEASE_ENV_DRIFT"):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            api=activated_api,
            livez_opener=livez,
        )


def test_candidate_rejects_canonical_domain_before_p4() -> None:
    app = _app(active_sha=EXPECTED_SHA)
    app["domains"] = [{"fqdn": CANDIDATE_HOST}, {"fqdn": "omnicio.ru"}]
    api = _Api(app)
    livez = _Livez()
    with pytest.raises(
        release.ReleaseStopped, match="TIMEWEB_APP_RELEASE_PREMATURE_CANONICAL_DOMAIN"
    ):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            api=api,
            livez_opener=livez,
        )


def test_deploy_requires_confirmation_and_mutates_only_exact_sha() -> None:
    api = _Api(_app())
    livez = _Livez()
    with pytest.raises(
        release.ReleaseStopped, match="TIMEWEB_APP_RELEASE_CONFIRMATION_REQUIRED"
    ):
        release.run(
            operation="deploy",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            api=api,
            livez_opener=livez,
        )
    assert api.calls == []

    last_known_good = release.run(
        operation="deploy",
        expected_sha=EXPECTED_SHA,
        observed_main_sha=EXPECTED_SHA,
        token="token",
        confirmation=release.DEPLOY_CONFIRMATION,
        api=api,
        livez_opener=livez,
    )
    assert api.calls == [("17", EXPECTED_SHA)]
    assert last_known_good == LKG_SHA


def test_wire_deploy_body_is_exact_commit_only() -> None:
    opener = _Opener(
        [
            _Response(
                {
                    "deploy": {
                        "id": "deploy-new",
                        "commit_sha": EXPECTED_SHA,
                        "status": "created",
                    }
                },
                status=201,
            )
        ]
    )
    api = release.TimewebAppApi("opaque-token", opener=opener, sleeper=lambda _: None)
    api.deploy_once("17", EXPECTED_SHA)
    assert len(opener.requests) == 1
    request = opener.requests[0]
    assert request.method == "POST"
    assert request.full_url == "https://api.timeweb.cloud/api/v1/apps/17/deploy"
    assert request.data is not None
    assert json.loads(request.data) == {"commit_sha": EXPECTED_SHA}
