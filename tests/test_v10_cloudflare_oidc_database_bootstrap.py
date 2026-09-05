from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

import apps.api.cf_d_database_bootstrap as proxy
import scripts.bootstrap_v10_cloudflare_production_database_via_staging as runner


ROOT = Path(__file__).resolve().parents[1]
FUNCTION_SOURCE = ROOT / "infrastructure/cloudflare/cf_d_neon_bootstrap/index.mjs"


EXPECTED_SHA = "a" * 40
_TEST_PASSWORD_MARKER = "synthetic-password-marker"


def _postgres_uri(role: str, host: str, *, channel_binding: bool = False) -> str:
    query = {"sslmode": "require"}
    if channel_binding:
        query["channel_binding"] = "require"
    return urlunsplit(
        (
            "postgresql",
            f"{role}:{_TEST_PASSWORD_MARKER}@{host}",
            "/neondb",
            urlencode(query),
            "",
        )
    )


VALID_STAGING_DSN = _postgres_uri(
    "omni_cio_cloudflare_staging",
    "ep-example.c-6.eu-central-1.aws.neon.tech",
)
VALID_PRODUCTION_DSN = _postgres_uri(
    "omni_cio_cloudflare_prod",
    "ep-example-pooler.c-6.eu-central-1.aws.neon.tech",
    channel_binding=True,
)


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _Connection:
    def __init__(self, branch: object = "br-example1234") -> None:
        self.branch = branch

    def execute(self, query: str) -> _Cursor:
        assert "neon.branch_id" in query
        return _Cursor((self.branch,))


class _Response:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        *,
        content: bytes | None = None,
        status_code: int = 200,
    ) -> None:
        self.status_code = status_code
        self.content = (
            json.dumps(payload).encode("utf-8") if content is None else content
        )
        self.bytes_yielded = 0

    def iter_bytes(self, chunk_size: int | None = None):  # type: ignore[no-untyped-def]
        size = chunk_size or max(1, len(self.content))
        for offset in range(0, len(self.content), size):
            chunk = self.content[offset : offset + size]
            self.bytes_yielded += len(chunk)
            yield chunk


class _StreamContext:
    def __init__(self, response: _Response) -> None:
        self.response = response

    def __enter__(self) -> _Response:
        return self.response

    def __exit__(
        self, exc_type, exc, traceback
    ) -> None:  # type: ignore[no-untyped-def]
        return None


class _Client:
    def __init__(self, response: _Response, **kwargs: object) -> None:
        self.response = response
        self.kwargs = kwargs
        self.authorization = ""
        self.url = ""
        self.streamed = False

    def __enter__(self) -> _Client:
        return self

    def __exit__(
        self, exc_type, exc, traceback
    ) -> None:  # type: ignore[no-untyped-def]
        return None

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, str],
    ) -> _StreamContext:
        assert method == "POST"
        self.url = url
        self.authorization = headers["Authorization"]
        self.streamed = True
        assert json == {"expected_sha": EXPECTED_SHA}
        return _StreamContext(self.response)


class CloudflareOidcDatabaseBootstrapTests(unittest.TestCase):
    def test_bootstrap_origin_is_derived_without_project_identifier(self) -> None:
        origin = proxy._bootstrap_origin(_Connection(), VALID_STAGING_DSN)
        self.assertEqual(
            origin,
            "https://br-example1234-cfdprodbootstrap.compute."
            "c-6.eu-central-1.aws.neon.tech/",
        )

    def test_bootstrap_origin_rejects_non_neon_region(self) -> None:
        dsn = VALID_STAGING_DSN.replace("eu-central-1", "us-east-1")
        with self.assertRaisesRegex(RuntimeError, "DATABASE_DSN_INVALID"):
            proxy._database_cell(dsn)

    def test_runtime_response_requires_exact_role_sha_and_tls(self) -> None:
        payload = {
            "status": "READY",
            "runtime_role": "omni_cio_cloudflare_prod",
            "runtime_dsn": VALID_PRODUCTION_DSN,
            "source_sha": EXPECTED_SHA,
        }
        self.assertEqual(
            proxy._runtime_dsn(payload, EXPECTED_SHA), VALID_PRODUCTION_DSN
        )
        self.assertEqual(
            runner._validate_runtime_payload(payload, EXPECTED_SHA),
            VALID_PRODUCTION_DSN,
        )
        with self.assertRaisesRegex(RuntimeError, "BOOTSTRAP_SHA_MISMATCH"):
            proxy._runtime_dsn(payload, "b" * 40)
        insecure = dict(payload)
        insecure["runtime_dsn"] = VALID_PRODUCTION_DSN.replace(
            "sslmode=require", "sslmode=disable"
        )
        with self.assertRaisesRegex(RuntimeError, "BOOTSTRAP_DSN_INVALID"):
            proxy._runtime_dsn(insecure, EXPECTED_SHA)

    def test_route_is_staging_only_and_forwards_bearer_without_logging_it(self) -> None:
        production = FastAPI()
        proxy.install_cf_d_database_bootstrap_route(
            production,
            connection=_Connection(),
            runtime_dsn=VALID_STAGING_DSN,
            release_sha=EXPECTED_SHA,
            runtime_role="omni_cio_cloudflare_prod",
        )
        self.assertFalse(
            any(route.path == proxy._BOOTSTRAP_PATH for route in production.routes)
        )

        payload = {
            "status": "READY",
            "runtime_role": "omni_cio_cloudflare_prod",
            "runtime_dsn": VALID_PRODUCTION_DSN,
            "source_sha": EXPECTED_SHA,
        }
        observed: list[_Client] = []

        def client_factory(**kwargs: object) -> _Client:
            client = _Client(_Response(payload), **kwargs)
            observed.append(client)
            return client

        staging = FastAPI()
        with mock.patch.object(proxy.httpx, "Client", side_effect=client_factory):
            proxy.install_cf_d_database_bootstrap_route(
                staging,
                connection=_Connection(),
                runtime_dsn=VALID_STAGING_DSN,
                release_sha=EXPECTED_SHA,
                runtime_role="omni_cio_cloudflare_staging",
            )
            response = TestClient(staging).post(
                proxy._BOOTSTRAP_PATH,
                headers={
                    "Authorization": "Bearer synthetic.jwt.token",
                    "X-Omni-Expected-Sha": EXPECTED_SHA,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["runtime_dsn"], VALID_PRODUCTION_DSN)
        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0].streamed)
        self.assertEqual(observed[0].authorization, "Bearer synthetic.jwt.token")
        self.assertNotIn("synthetic.jwt.token", repr(response.headers))

    def test_route_stops_streaming_when_provider_response_exceeds_budget(self) -> None:
        raw = b"x" * (
            proxy._MAX_PROVIDER_RESPONSE_BYTES
            + (proxy._PROVIDER_STREAM_CHUNK_BYTES * 3)
        )
        provider_response = _Response(content=raw)
        observed: list[_Client] = []

        def client_factory(**kwargs: object) -> _Client:
            client = _Client(provider_response, **kwargs)
            observed.append(client)
            return client

        staging = FastAPI()
        with mock.patch.object(proxy.httpx, "Client", side_effect=client_factory):
            proxy.install_cf_d_database_bootstrap_route(
                staging,
                connection=_Connection(),
                runtime_dsn=VALID_STAGING_DSN,
                release_sha=EXPECTED_SHA,
                runtime_role="omni_cio_cloudflare_staging",
            )
            response = TestClient(staging).post(
                proxy._BOOTSTRAP_PATH,
                headers={
                    "Authorization": "Bearer synthetic.jwt.token",
                    "X-Omni-Expected-Sha": EXPECTED_SHA,
                },
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_TOO_LARGE",
        )
        self.assertEqual(len(observed), 1)
        self.assertLess(provider_response.bytes_yielded, len(raw))
        self.assertLessEqual(
            provider_response.bytes_yielded,
            proxy._MAX_PROVIDER_RESPONSE_BYTES + proxy._PROVIDER_STREAM_CHUNK_BYTES,
        )

    def test_runner_accepts_only_github_oidc_request_host_and_custom_audience(
        self,
    ) -> None:
        url = runner._oidc_request_url(
            "https://pipelines.actions.githubusercontent.com/example?api-version=2.0"
        )
        parsed = urlsplit(url)
        self.assertEqual(parsed.hostname, "pipelines.actions.githubusercontent.com")
        self.assertEqual(parse_qs(parsed.query)["audience"], [runner._AUDIENCE])
        with self.assertRaisesRegex(
            runner.BootstrapStopped, "GITHUB_OIDC_REQUEST_URL_INVALID"
        ):
            runner._oidc_request_url("https://example.com/token")

    def test_runner_accepts_only_exact_staging_workers_dev_origin(self) -> None:
        origin = runner._validated_staging_origin(
            "https://omni-cio-v10-web-staging.example.workers.dev/"
        )
        self.assertEqual(
            origin, "https://omni-cio-v10-web-staging.example.workers.dev"
        )
        with self.assertRaisesRegex(runner.BootstrapStopped, "STAGING_ORIGIN_INVALID"):
            runner._validated_staging_origin("https://example.com/")

    def test_runner_writes_dsn_only_after_platform_permissions_are_hardened(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.dict(
                runner.os.environ, {"RUNNER_TEMP": str(root)}, clear=False
            ):
                path = runner._output_file()
                runner._write_private_file(path, VALID_PRODUCTION_DSN)
                self.assertEqual(
                    path.read_text(encoding="utf-8").strip(), VALID_PRODUCTION_DSN
                )
                if runner.os.name != "nt":
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_runner_refuses_to_overwrite_preexisting_private_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.dict(
                runner.os.environ, {"RUNNER_TEMP": str(root)}, clear=False
            ):
                path = runner._output_file()
                path.write_text("preexisting-marker\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    runner.BootstrapStopped, "DSN_ALREADY_EXISTS"
                ):
                    runner._write_private_file(path, VALID_PRODUCTION_DSN)
                self.assertEqual(
                    path.read_text(encoding="utf-8"), "preexisting-marker\n"
                )

    def test_runner_removes_empty_file_when_permission_hardening_fails(self) -> None:
        helper_name = (
            "_harden_windows_private_file"
            if runner.os.name == "nt"
            else "_harden_posix_private_file"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                mock.patch.dict(
                    runner.os.environ, {"RUNNER_TEMP": str(root)}, clear=False
                ),
                mock.patch.object(
                    runner,
                    helper_name,
                    side_effect=runner.BootstrapStopped("synthetic-permission-failure"),
                ),
            ):
                path = runner._output_file()
                with self.assertRaisesRegex(
                    runner.BootstrapStopped, "synthetic-permission-failure"
                ):
                    runner._write_private_file(path, VALID_PRODUCTION_DSN)
                self.assertFalse(path.exists())

    def test_windows_acl_hardening_uses_exact_sid_allowlist_and_minimal_env(
        self,
    ) -> None:
        target = Path("C:/synthetic-runner-temp/private-dsn.txt")
        completed = mock.Mock(returncode=0)
        sensitive = "synthetic-oidc-request-token"
        with (
            mock.patch.dict(
                runner.os.environ,
                {
                    "SystemRoot": "C:\\Windows",
                    "PATH": "C:\\Windows\\System32",
                    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": sensitive,
                },
                clear=True,
            ),
            mock.patch.object(
                runner, "_powershell_executable", return_value="powershell.exe"
            ),
            mock.patch.object(
                runner.subprocess, "run", return_value=completed
            ) as run_mock,
        ):
            runner._harden_windows_private_file(target)

        command = run_mock.call_args.args[0]
        script = command[-1]
        self.assertIn("SetAccessRuleProtection($true, $false)", script)
        self.assertIn('S-1-5-18', script)
        self.assertIn('S-1-5-32-544', script)
        self.assertIn("AreAccessRulesProtected", script)
        self.assertNotIn(str(target), script)
        environment = run_mock.call_args.kwargs["env"]
        self.assertEqual(environment[runner._WINDOWS_ACL_PATH_ENV], str(target))
        self.assertNotIn("ACTIONS_ID_TOKEN_REQUEST_TOKEN", environment)
        self.assertNotIn(sensitive, repr(environment))
        self.assertIs(run_mock.call_args.kwargs["stdout"], runner.subprocess.DEVNULL)
        self.assertIs(run_mock.call_args.kwargs["stderr"], runner.subprocess.DEVNULL)
        self.assertEqual(
            run_mock.call_args.kwargs["timeout"], runner._WINDOWS_ACL_TIMEOUT_SECONDS
        )

    def test_windows_acl_hardening_fails_closed_on_acl_rejection(self) -> None:
        target = Path("C:/synthetic-runner-temp/private-dsn.txt")
        with (
            mock.patch.object(
                runner, "_powershell_executable", return_value="powershell.exe"
            ),
            mock.patch.object(
                runner.subprocess, "run", return_value=mock.Mock(returncode=47)
            ),
        ):
            with self.assertRaisesRegex(
                runner.BootstrapStopped, "DSN_ACL_HARDENING_FAILED"
            ):
                runner._harden_windows_private_file(target)

    def test_neon_function_refreshes_jwks_once_on_unknown_kid(self) -> None:
        source = FUNCTION_SOURCE.read_text(encoding="utf-8")
        start = source.index("async function signingKeyForKid(kid)")
        end = source.index("async function verifyOidcToken", start)
        section = source[start:end]
        self.assertIn("if (candidates.length === 0)", section)
        self.assertEqual(section.count("loadJwks(true)"), 1)
        self.assertLess(
            section.index("loadJwks(true)"),
            section.index("if (candidates.length !== 1)"),
        )

    def test_neon_function_source_enforces_oidc_and_least_privilege_markers(
        self,
    ) -> None:
        source = FUNCTION_SOURCE.read_text(encoding="utf-8")
        required = (
            "https://token.actions.githubusercontent.com",
            "omni-cio-cf-d-production-database-bootstrap",
            "repository_visibility !== 'private'",
            "claims.ref !== EXPECTED_REF",
            "claims.workflow_ref !== EXPECTED_WORKFLOW_REF",
            "claims.workflow_sha !== expectedSha",
            "claims.sha !== expectedSha",
            "claims.runner_environment !== 'self-hosted'",
            "omni_cio_cloudflare_prod",
            "createHmac('sha384'",
            "omni-cio-v10/cloudflare-production/runtime-password/v1",
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
            "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
            "FORCE ROW LEVEL SECURITY",
            "CLOUDFLARE_RUNTIME_DATABASE_OWNERSHIP_FORBIDDEN",
            "CLOUDFLARE_RUNTIME_OBJECT_OWNERSHIP_FORBIDDEN",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        for forbidden in (
            "console.log",
            "NEON_API_KEY",
            "billowing-smoke",
            "br-floral-firefly",
            "postgresql://neondb_owner:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
