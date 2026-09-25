from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from urllib.request import Request

from scripts import timeweb_public_ingress_acceptance as ingress


ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "scripts/check_v10_timeweb_public_ingress_acceptance.py"
SPEC = importlib.util.spec_from_file_location(
    "check_v10_timeweb_public_ingress_acceptance",
    GUARD_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

EXPECTED_SHA = "a" * 40
ROLLBACK_SHA = "b" * 40
DIGEST = "c" * 64


def _security_headers(*, api: bool) -> dict[str, str]:
    return {
        "Strict-Transport-Security": "max-age=31536000",
        "Content-Security-Policy": (
            "default-src 'self'; base-uri 'none'; object-src 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        ),
        "Cross-Origin-Opener-Policy": "same-origin",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "same-origin",
        "Vary": "Origin, Sec-Fetch-Site",
        "Cache-Control": "no-store" if api else "no-cache",
        "Content-Type": "application/json" if api else "text/html; charset=utf-8",
        "Server": "nginx",
    }


class _Response:
    def __init__(
        self,
        payload: object,
        *,
        api: bool,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = 200
        self.headers = headers or _security_headers(api=api)
        if api:
            self._raw = json.dumps(payload).encode("utf-8")
        else:
            self._raw = str(payload).encode("utf-8")

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


def _opener(
    sha: str = EXPECTED_SHA,
    *,
    live_headers: dict[str, str] | None = None,
) -> _Opener:
    return _Opener(
        [
            _Response(
                {"status": "ok", "release_sha": sha},
                api=True,
                headers=live_headers,
            ),
            _Response(
                {
                    "status": "ok",
                    "release_sha": sha,
                    "database": "READY",
                    "synthetic_preview": False,
                },
                api=True,
            ),
            _Response("<!doctype html><html><body>Omni-CIO</body></html>", api=False),
        ]
    )


def _app(*, domain: str = "omnicio.ru", public: str = "false") -> dict[str, object]:
    return {
        "id": 17,
        "name": "omni-cio-v10",
        "type": "backend",
        "framework": "docker",
        "branch_name": "main",
        "repository": {"full_name": "MishaGameHacking/omni-cio-gateway"},
        "is_auto_deploy": False,
        "status": "active",
        "commit_sha": EXPECTED_SHA,
        "domains": [
            {"fqdn": "technical.example.invalid"},
            {"fqdn": domain},
        ],
        "envs": {
            "OMNI_V10_HOSTED_RUNTIME": "1",
            "OMNI_V10_PUBLIC_HOSTNAME": "omnicio.ru",
            "OMNI_V10_RELEASE_SHA": EXPECTED_SHA,
            "OMNI_V10_POSTGRES_RUNTIME_ROLE": "omni_cio_hosted_api",
            "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED": "true",
            "PUBLIC_MULTI_USER_ENABLED": public,
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "false",
            "OMNI_V10_POSTGRES_DSN": "postgresql://opaque",
        },
    }


class _Api:
    def __init__(self, app: dict[str, object]) -> None:
        self.app = app
        self.read_calls: list[str] = []

    def list_apps(self) -> dict[str, object]:
        self.read_calls.append("list_apps")
        return {"apps": [self.app]}

    def get_app(self, app_id: str) -> dict[str, object]:
        self.read_calls.append(f"get_app:{app_id}")
        return {"app": self.app}

    def list_deploys(self, app_id: str) -> dict[str, object]:
        self.read_calls.append(f"list_deploys:{app_id}")
        return {
            "deploys": [
                {"id": "current", "commit_sha": EXPECTED_SHA, "status": "success"},
                {"id": "rollback", "commit_sha": ROLLBACK_SHA, "status": "success"},
            ]
        }


def _accept(api: _Api, *, opener: _Opener | None = None) -> None:
    ingress.run(
        operation="accept",
        expected_sha=EXPECTED_SHA,
        observed_main_sha=EXPECTED_SHA,
        confirmation=ingress.ACCEPT_CONFIRMATION,
        p3_recovery_evidence_sha256=DIGEST,
        russian_no_vpn_evidence_sha256=DIGEST,
        rollback_release_sha=ROLLBACK_SHA,
        rollback_evidence_sha256=DIGEST,
        api=api,
        opener=opener or _opener(),
    )


class TimewebPublicIngressTests(unittest.TestCase):
    def test_repository_guard_passes(self) -> None:
        guard.validate(ROOT)

    def test_guard_requires_certified_p4_state_after_transition(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        for row in payload["branch_milestones"]:
            if row["id"] == "P4_OMNICIO_RU_DNS_TLS":
                row["state"] = "IMPLEMENTED_VERIFICATION_PENDING"
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_PUBLIC_INGRESS_MILESTONE_DRIFT",
        ):
            guard._validate_contract(payload)

    def test_observe_accepts_exact_public_runtime_without_provider_access(self) -> None:
        opener = _opener()
        ingress.run(
            operation="observe",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            opener=opener,
        )
        self.assertEqual(
            [request.full_url for request in opener.requests],
            [
                "https://omnicio.ru/livez",
                "https://omnicio.ru/healthz",
                "https://omnicio.ru/",
            ],
        )

    def test_observe_rejects_release_sha_drift(self) -> None:
        opener = _opener(ROLLBACK_SHA)
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_RELEASE_SHA_DRIFT",
        ):
            ingress.run(
                operation="observe",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                opener=opener,
            )

    def test_observe_rejects_retired_edge_header(self) -> None:
        headers = _security_headers(api=True)
        headers["CF-Ray"] = "synthetic"
        opener = _opener(live_headers=headers)
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_RETIRED_EDGE_HEADER",
        ):
            ingress.run(
                operation="observe",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                opener=opener,
            )

    def test_accept_rejects_missing_canonical_domain(self) -> None:
        api = _Api(_app(domain="technical.example.invalid"))
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_CANONICAL_DOMAIN_MISSING",
        ):
            _accept(api)

    def test_accept_rejects_premature_public_activation(self) -> None:
        api = _Api(_app(public="true"))
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_ENV_DRIFT",
        ):
            _accept(api)

    def test_accept_requires_recovery_evidence(self) -> None:
        api = _Api(_app())
        opener = _opener()
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_P3_RECOVERY_EVIDENCE_INVALID",
        ):
            ingress.run(
                operation="accept",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                confirmation=ingress.ACCEPT_CONFIRMATION,
                russian_no_vpn_evidence_sha256=DIGEST,
                rollback_release_sha=ROLLBACK_SHA,
                rollback_evidence_sha256=DIGEST,
                api=api,
                opener=opener,
            )

    def test_accept_uses_read_only_provider_surface_and_proves_rollback(self) -> None:
        api = _Api(_app())
        _accept(api)
        self.assertEqual(
            api.read_calls,
            ["list_apps", "get_app:17", "list_deploys:17"],
        )

    def test_observe_rejects_hsts_downgrade(self) -> None:
        headers = _security_headers(api=True)
        headers["Strict-Transport-Security"] = "max-age=300"
        opener = _opener(live_headers=headers)
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_HSTS_INVALID",
        ):
            ingress.run(
                operation="observe",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                opener=opener,
            )

    def test_observe_rejects_duplicate_hsts_directive(self) -> None:
        headers = _security_headers(api=True)
        headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; max-age=0"
        )
        opener = _opener(live_headers=headers)
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_HSTS_INVALID",
        ):
            ingress.run(
                operation="observe",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                opener=opener,
            )

    def test_observe_rejects_csp_substring_spoof(self) -> None:
        headers = _security_headers(api=True)
        headers["Content-Security-Policy"] = (
            "x-default-src 'self'; base-uri 'none'; object-src 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        opener = _opener(live_headers=headers)
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_CSP_INVALID",
        ):
            ingress.run(
                operation="observe",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                opener=opener,
            )

    def test_accept_rejects_truncated_provider_pagination(self) -> None:
        api = _Api(_app())
        original = api.list_apps

        def paginated_apps() -> dict[str, object]:
            payload = original()
            payload["meta"] = {"total": 101}
            return payload

        api.list_apps = paginated_apps  # type: ignore[method-assign]
        with self.assertRaisesRegex(
            ingress.PublicIngressStopped,
            "TIMEWEB_PUBLIC_INGRESS_APPS_INVALID",
        ):
            _accept(api)

    def test_guard_rejects_provider_mutation_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (
                guard.CONTRACT_RELATIVE,
                guard.CONTROLLER_RELATIVE,
                guard.WORKFLOW_RELATIVE,
                guard.RUNBOOK_RELATIVE,
            ):
                source = ROOT / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            controller = root / guard.CONTROLLER_RELATIVE
            controller.write_text(
                controller.read_text(encoding="utf-8")
                + "\n# mutation regression: api.deploy_once(app_id, sha)\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_PUBLIC_INGRESS_CONTROLLER_AUTHORITY_WIDENED",
            ):
                guard.validate(root)


if __name__ == "__main__":
    unittest.main()
