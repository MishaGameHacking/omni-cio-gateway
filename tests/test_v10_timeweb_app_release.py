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


class _RawResponse:
    def __init__(self, raw: bytes, *, status: int = 200) -> None:
        self.status = status
        self._raw = raw

    def read(self, amount: int = -1) -> bytes:
        return self._raw if amount < 0 else self._raw[:amount]

    def __enter__(self) -> _RawResponse:
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
    def __init__(
        self,
        sha: str = EXPECTED_SHA,
        *,
        health_status: str = "ok",
        database: str = "READY",
        synthetic_preview: bool = False,
    ) -> None:
        self.sha = sha
        self.health_status = health_status
        self.database = database
        self.synthetic_preview = synthetic_preview

    def open(self, request: Request, *, timeout: float) -> _Response:
        del timeout
        if request.full_url.endswith("/healthz"):
            return _Response(
                {
                    "status": self.health_status,
                    "release_sha": self.sha,
                    "database": self.database,
                    "synthetic_preview": self.synthetic_preview,
                }
            )
        return _Response({"status": "ok", "release_sha": self.sha})


class _SequenceLivez:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)

    def open(self, request: Request, *, timeout: float) -> _Response:
        del request, timeout
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        if not isinstance(value, _Response):
            raise AssertionError("unexpected livez fixture")
        return value


def _app(
    *,
    active_sha: str = LKG_SHA,
    status: str = "active",
    runtime_mode: str = release.RUNTIME_MODE_PREACTIVATION,
) -> dict[str, object]:
    live = runtime_mode == release.RUNTIME_MODE_LIVE_OPERABLE
    domains = [{"fqdn": CANDIDATE_HOST}]
    if live:
        domains.append({"fqdn": "omnicio.ru"})
    activation = "true" if live else "false"
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
        "domains": domains,
        "envs": {
            "OMNI_V10_HOSTED_RUNTIME": "1",
            "OMNI_V10_PUBLIC_HOSTNAME": "omnicio.ru",
            "OMNI_V10_CANDIDATE_HOSTNAME": CANDIDATE_HOST,
            "OMNI_V10_RELEASE_SHA": EXPECTED_SHA,
            "OMNI_V10_POSTGRES_RUNTIME_ROLE": "omni_cio_hosted_api",
            "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED": "true",
            "PUBLIC_MULTI_USER_ENABLED": activation,
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED": activation,
            "OMNI_V10_POSTGRES_DSN": "postgresql://opaque",
            "OMNI_V10_POSTGRES_PRIVATE_HOSTADDR": "10.0.0.10",
            "OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR": "10.0.0.0/24",
        },
    }


class _Api:
    def __init__(self, app: dict[str, object]) -> None:
        self.app_payload = app
        self.rows = [
            {
                "id": "deploy-lkg",
                "commit_sha": LKG_SHA,
                "status": "success",
                "ended_at": "2026-09-25T12:00:00Z",
            }
        ]
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


class _InflightApi(_Api):
    def __init__(self, app: dict[str, object]) -> None:
        super().__init__(app)
        self.rows.insert(
            0,
            {"id": "deploy-inflight", "commit_sha": EXPECTED_SHA, "status": "created"},
        )
        self.deploy_reads = 0

    def list_deploys(self, app_id: str) -> dict[str, object]:
        self.deploy_reads += 1
        if self.deploy_reads >= 2:
            self.rows[0]["status"] = "success"
            self.app_payload["commit_sha"] = EXPECTED_SHA
            self.app_payload["status"] = "active"
        return super().list_deploys(app_id)


class _AmbiguousApi(_Api):
    def deploy_once(self, app_id: str, sha: str) -> dict[str, object]:
        self.calls.append((app_id, sha))
        row = {"id": "deploy-ambiguous", "commit_sha": sha, "status": "success"}
        self.rows.insert(0, row)
        self.app_payload["commit_sha"] = sha
        self.app_payload["status"] = "active"
        raise release.AmbiguousDeploy


class _MalformedSuccessApi(_Api):
    def deploy_once(self, app_id: str, sha: str) -> dict[str, object]:
        self.calls.append((app_id, sha))
        row = {"id": "deploy-malformed", "commit_sha": sha, "status": "success"}
        self.rows.insert(0, row)
        self.app_payload["commit_sha"] = sha
        self.app_payload["status"] = "active"
        return {"deploy": {"unexpected": "successful-but-unprovable-response"}}


def _assert_observe_stops(app: dict[str, object], code: str) -> None:
    api = _Api(app)
    livez = _Livez()
    with pytest.raises(release.ReleaseStopped, match=code):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            api=api,
            livez_opener=livez,
        )


def _assert_healthz_stops(opener: _Livez, code: str) -> None:
    with pytest.raises(release.ReleaseStopped, match=code):
        release._verify_healthz(
            CANDIDATE_HOST,
            EXPECTED_SHA,
            opener=opener,
        )


def test_provider_ids_reject_bool_none_and_fractional_values() -> None:
    for value in (True, False, None, 1.5, [], {}):
        with pytest.raises(
            release.ReleaseStopped,
            match="TIMEWEB_APP_RELEASE_APP_ID_INVALID",
        ):
            release._safe_id(value, "TIMEWEB_APP_RELEASE_APP_ID_INVALID")
    assert release._safe_id(17, "TIMEWEB_APP_RELEASE_APP_ID_INVALID") == "17"
    assert (
        release._safe_id("deploy-17", "TIMEWEB_APP_RELEASE_APP_ID_INVALID")
        == "deploy-17"
    )


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


def test_candidate_requires_scoped_private_database_route() -> None:
    missing = _app(active_sha=EXPECTED_SHA)
    assert isinstance(missing["envs"], dict)
    missing["envs"].pop("OMNI_V10_POSTGRES_PRIVATE_HOSTADDR")
    _assert_observe_stops(
        missing,
        "TIMEWEB_APP_RELEASE_PRIVATE_ROUTE_REQUIRED",
    )

    public_target = _app(active_sha=EXPECTED_SHA)
    assert isinstance(public_target["envs"], dict)
    public_target["envs"]["OMNI_V10_POSTGRES_PRIVATE_HOSTADDR"] = "8.8.8.8"
    _assert_observe_stops(
        public_target,
        "TIMEWEB_APP_RELEASE_PRIVATE_ROUTE_INVALID",
    )

    mismatched = _app(active_sha=EXPECTED_SHA)
    assert isinstance(mismatched["envs"], dict)
    mismatched["envs"]["OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR"] = "10.0.1.0/24"
    _assert_observe_stops(
        mismatched,
        "TIMEWEB_APP_RELEASE_PRIVATE_ROUTE_INVALID",
    )


def test_healthz_requires_real_database_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(release.time, "sleep", lambda _seconds: None)

    unavailable = _Livez(health_status="unavailable", database="NOT_READY")
    _assert_healthz_stops(
        unavailable,
        "TIMEWEB_APP_RELEASE_HEALTHZ_DATABASE_NOT_READY",
    )

    synthetic = _Livez(synthetic_preview=True)
    _assert_healthz_stops(
        synthetic,
        "TIMEWEB_APP_RELEASE_HEALTHZ_SYNTHETIC_PREVIEW_FORBIDDEN",
    )

    stale_release = _Livez(sha=LKG_SHA)
    _assert_healthz_stops(
        stale_release,
        "TIMEWEB_APP_RELEASE_HEALTHZ_SHA_DRIFT",
    )

def test_healthz_retries_transient_unavailability_until_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _SequenceLivez(
        [
            _Response({"status": "unavailable"}, status=503),
            _Response(
                {
                    "status": "ok",
                    "release_sha": EXPECTED_SHA,
                    "database": "READY",
                    "synthetic_preview": False,
                }
            ),
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(release.time, "sleep", sleeps.append)

    release._verify_healthz(CANDIDATE_HOST, EXPECTED_SHA, opener=opener)

    assert sleeps == [release._HEALTHZ_RETRY_DELAYS[0]]


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


def test_live_operable_release_requires_p5_evidence_and_canonical_domain() -> None:
    app = _app(
        active_sha=EXPECTED_SHA,
        runtime_mode=release.RUNTIME_MODE_LIVE_OPERABLE,
    )
    api = _Api(app)
    livez = _Livez()
    with pytest.raises(
        release.ReleaseStopped,
        match="TIMEWEB_APP_RELEASE_P5_LIVE_EVIDENCE_REQUIRED",
    ):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            runtime_mode=release.RUNTIME_MODE_LIVE_OPERABLE,
            api=api,
            livez_opener=livez,
        )

    last_known_good = release.run(
        operation="observe",
        expected_sha=EXPECTED_SHA,
        observed_main_sha=EXPECTED_SHA,
        token="token",
        runtime_mode=release.RUNTIME_MODE_LIVE_OPERABLE,
        p5_live_evidence_sha256="c" * 64,
        api=api,
        livez_opener=livez,
    )
    assert last_known_good == LKG_SHA

    app["domains"] = [{"fqdn": CANDIDATE_HOST}]
    with pytest.raises(
        release.ReleaseStopped,
        match="TIMEWEB_APP_RELEASE_CANONICAL_DOMAIN_REQUIRED",
    ):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            runtime_mode=release.RUNTIME_MODE_LIVE_OPERABLE,
            p5_live_evidence_sha256="c" * 64,
            api=api,
            livez_opener=livez,
        )


def test_live_operable_release_rejects_partial_activation() -> None:
    app = _app(
        active_sha=EXPECTED_SHA,
        runtime_mode=release.RUNTIME_MODE_LIVE_OPERABLE,
    )
    assert isinstance(app["envs"], dict)
    app["envs"]["OMNI_V10_TELEGRAM_LOGIN_ENABLED"] = "false"
    api = _Api(app)
    livez = _Livez()

    with pytest.raises(release.ReleaseStopped, match="TIMEWEB_APP_RELEASE_ENV_DRIFT"):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            runtime_mode=release.RUNTIME_MODE_LIVE_OPERABLE,
            p5_live_evidence_sha256="c" * 64,
            api=api,
            livez_opener=livez,
        )


def test_preactivation_release_rejects_live_evidence() -> None:
    api = _Api(_app(active_sha=EXPECTED_SHA))
    livez = _Livez()

    with pytest.raises(
        release.ReleaseStopped,
        match="TIMEWEB_APP_RELEASE_UNEXPECTED_P5_LIVE_EVIDENCE",
    ):
        release.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            p5_live_evidence_sha256="c" * 64,
            api=api,
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


def test_livez_reconciles_transport_and_stale_release_propagation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _SequenceLivez(
        [
            OSError("transient route propagation"),
            _Response({"status": "ok", "release_sha": LKG_SHA}),
            _Response({"status": "ok", "release_sha": EXPECTED_SHA}),
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(release.time, "sleep", sleeps.append)
    release._verify_livez(CANDIDATE_HOST, EXPECTED_SHA, opener=opener)
    assert sleeps == list(release._LIVEZ_RETRY_DELAYS[:2])


def test_deploy_wait_budget_is_multi_minute_and_workflow_bounded() -> None:
    budget = sum(release._POLL_DELAYS)
    livez_budget = sum(release._LIVEZ_RETRY_DELAYS)
    healthz_budget = sum(release._HEALTHZ_RETRY_DELAYS)
    assert budget >= 300.0
    assert budget < 15 * 60
    assert sum(release._DEPLOY_RECONCILE_DELAYS) >= 60.0
    assert livez_budget >= 120.0
    assert livez_budget < 5 * 60
    assert healthz_budget >= 120.0
    assert healthz_budget < 5 * 60


def test_last_known_good_uses_provider_completion_time_not_list_order() -> None:
    older = "c" * 40
    newer = "d" * 40
    rows = [
        {
            "id": "deploy-older",
            "commit_sha": older,
            "status": "success",
            "ended_at": "2026-09-24T12:00:00Z",
        },
        {
            "id": "deploy-newer",
            "commit_sha": newer,
            "status": "success",
            "ended_at": "2026-09-25T12:00:00+00:00",
        },
    ]
    assert release._last_known_good(rows, EXPECTED_SHA) == newer
    rows.reverse()
    assert release._last_known_good(rows, EXPECTED_SHA) == newer


def test_last_known_good_rejects_ambiguous_latest_completion() -> None:
    rows = [
        {
            "id": "deploy-a",
            "commit_sha": "c" * 40,
            "status": "success",
            "ended_at": "2026-09-25T12:00:00Z",
        },
        {
            "id": "deploy-b",
            "commit_sha": "d" * 40,
            "status": "success",
            "ended_at": "2026-09-25T12:00:00+00:00",
        },
    ]
    with pytest.raises(
        release.ReleaseStopped,
        match="TIMEWEB_APP_RELEASE_LKG_HISTORY_AMBIGUOUS",
    ):
        release._last_known_good(rows, EXPECTED_SHA)


def test_last_known_good_requires_completed_provider_timestamp() -> None:
    with pytest.raises(
        release.ReleaseStopped,
        match="TIMEWEB_APP_RELEASE_DEPLOY_ENDED_AT_INVALID",
    ):
        release._last_known_good(
            [
                {
                    "id": "deploy-lkg",
                    "commit_sha": LKG_SHA,
                    "status": "success",
                }
            ],
            EXPECTED_SHA,
        )


def test_deploy_adopts_unique_inflight_exact_sha_without_second_post() -> None:
    api = _InflightApi(_app())
    last_known_good = release.run(
        operation="deploy",
        expected_sha=EXPECTED_SHA,
        observed_main_sha=EXPECTED_SHA,
        token="token",
        confirmation=release.DEPLOY_CONFIRMATION,
        api=api,
        livez_opener=_Livez(),
    )
    assert api.calls == []
    assert last_known_good == LKG_SHA


def test_deploy_rejects_multiple_inflight_exact_sha_before_mutation() -> None:
    api = _Api(_app())
    api.rows[:0] = [
        {"id": "deploy-a", "commit_sha": EXPECTED_SHA, "status": "created"},
        {"id": "deploy-b", "commit_sha": EXPECTED_SHA, "status": "started"},
    ]
    livez = _Livez()
    with pytest.raises(
        release.ReleaseStopped,
        match="TIMEWEB_APP_RELEASE_MULTIPLE_INFLIGHT_EXACT_SHA",
    ):
        release.run(
            operation="deploy",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            token="token",
            confirmation=release.DEPLOY_CONFIRMATION,
            api=api,
            livez_opener=livez,
        )
    assert api.calls == []


def test_ambiguous_deploy_reconciles_by_get_without_second_post() -> None:
    api = _AmbiguousApi(_app())
    last_known_good = release.run(
        operation="deploy",
        expected_sha=EXPECTED_SHA,
        observed_main_sha=EXPECTED_SHA,
        token="token",
        confirmation=release.DEPLOY_CONFIRMATION,
        api=api,
        livez_opener=_Livez(),
    )
    assert api.calls == [("17", EXPECTED_SHA)]
    assert last_known_good == LKG_SHA


def test_wire_deploy_history_paginates_all_pages_without_truncation() -> None:
    rows = [
        {
            "id": f"deploy-{index}",
            "commit_sha": EXPECTED_SHA,
            "status": "success",
        }
        for index in range(101)
    ]
    opener = _Opener(
        [
            _Response({"deploys": rows[:100], "meta": {"total": 101}}),
            _Response({"deploys": rows[100:], "meta": {"total": 101}}),
        ]
    )
    api = release.TimewebAppApi("opaque-token", opener=opener, sleeper=lambda _: None)

    payload = api.list_deploys("17")

    assert payload["deploys"] == rows
    assert payload["meta"] == {"total": 101}
    assert [request.full_url for request in opener.requests] == [
        "https://api.timeweb.cloud/api/v1/apps/17/deploys?limit=100&offset=0",
        "https://api.timeweb.cloud/api/v1/apps/17/deploys?limit=100&offset=100",
    ]


def test_wire_deploy_history_rejects_duplicate_identity_across_pages() -> None:
    rows = [
        {
            "id": f"deploy-{index}",
            "commit_sha": EXPECTED_SHA,
            "status": "success",
        }
        for index in range(100)
    ]
    duplicate = {
        "id": "deploy-0",
        "commit_sha": LKG_SHA,
        "status": "success",
    }
    opener = _Opener(
        [
            _Response({"deploys": rows, "meta": {"total": 101}}),
            _Response({"deploys": [duplicate], "meta": {"total": 101}}),
        ]
    )
    api = release.TimewebAppApi("opaque-token", opener=opener, sleeper=lambda _: None)

    with pytest.raises(
        release.ReleaseStopped,
        match="TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_DUPLICATE_ID",
    ):
        api.list_deploys("17")


def test_wire_deploy_history_rejects_total_drift_between_pages() -> None:
    rows = [
        {
            "id": f"deploy-{index}",
            "commit_sha": EXPECTED_SHA,
            "status": "success",
        }
        for index in range(101)
    ]
    opener = _Opener(
        [
            _Response({"deploys": rows[:100], "meta": {"total": 101}}),
            _Response({"deploys": rows[100:], "meta": {"total": 102}}),
        ]
    )
    api = release.TimewebAppApi("opaque-token", opener=opener, sleeper=lambda _: None)

    with pytest.raises(
        release.ReleaseStopped,
        match="TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_CHANGED",
    ):
        api.list_deploys("17")


def test_successful_but_unprovable_deploy_response_reconciles_by_get() -> None:
    api = _MalformedSuccessApi(_app())
    last_known_good = release.run(
        operation="deploy",
        expected_sha=EXPECTED_SHA,
        observed_main_sha=EXPECTED_SHA,
        token="token",
        confirmation=release.DEPLOY_CONFIRMATION,
        api=api,
        livez_opener=_Livez(),
    )
    assert api.calls == [("17", EXPECTED_SHA)]
    assert last_known_good == LKG_SHA


def test_wire_unprovable_201_is_ambiguous_and_never_replayed() -> None:
    for raw in (
        b"{not-json",
        b"x" * (release.MAX_RESPONSE_BYTES + 1),
    ):
        opener = _Opener([_RawResponse(raw, status=201)])
        api = release.TimewebAppApi(
            "opaque-token",
            opener=opener,
            sleeper=lambda _: None,
        )
        with pytest.raises(release.AmbiguousDeploy):
            api.deploy_once("17", EXPECTED_SHA)
        assert len(opener.requests) == 1


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
