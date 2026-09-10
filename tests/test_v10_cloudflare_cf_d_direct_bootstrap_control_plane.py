from __future__ import annotations

import json
from pathlib import Path
import secrets
import ssl
import tempfile
from unittest import mock

import scripts.bootstrap_v10_cloudflare_production_database_direct as direct
import scripts.bootstrap_v10_cloudflare_production_database_via_staging as legacy


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
CANDIDATE_RUNNER = ROOT / "scripts/run_v10_cloudflare_gated_candidate.py"
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
FUNCTION_SOURCE = ROOT / "infrastructure/cloudflare/cf_d_neon_bootstrap/index.mjs"
EXPECTED_SHA = "a" * 40
ORIGIN = (
    "https://br-example1234-cfdprodbootstrap.compute."
    "c-6.eu-central-1.aws.neon.tech/"
)


def _oidc_token() -> str:
    return ".".join(secrets.token_urlsafe(18) for _ in range(3))


def _production_dsn() -> str:
    credential = secrets.token_urlsafe(32)
    return (
        "postgresql://omni_cio_cloudflare_prod:"
        f"{credential}@ep-example-pooler.c-6.eu-central-1.aws.neon.tech/neondb?"
        "sslmode=require&channel_binding=require"
    )


def test_direct_bootstrap_handoff_persists_only_validated_target_descriptor() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with mock.patch.dict(
            legacy.os.environ, {"RUNNER_TEMP": str(root)}, clear=False
        ):
            path = direct.write_bootstrap_origin_handoff(ORIGIN)
            assert path == root.resolve() / direct._BOOTSTRAP_ORIGIN_FILENAME
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload == {"branch_id": "br-example1234", "cell": "c-6"}
            assert "https://" not in path.read_text(encoding="utf-8")
            assert ".neon.tech" not in path.read_text(encoding="utf-8")
            expected_target = direct.BootstrapFunctionTarget(
                branch_id="br-example1234",
                cell="c-6",
            )
            assert direct.read_bootstrap_origin_handoff() == expected_target
            if legacy.os.name != "nt":
                assert path.stat().st_mode & 0o777 == 0o600
            direct._discard_origin_handoff(path)
            assert not path.exists()


def test_direct_bootstrap_target_rejects_arbitrary_network_destination() -> None:
    for value in (
        "https://example.com/",
        (
            "http://br-example1234-cfdprodbootstrap.compute.c-6."
            "eu-central-1.aws.neon.tech/"
        ),
        (
            "https://br-example1234-cfdprodbootstrap.compute.c-6."
            "eu-central-1.aws.neon.tech/path"
        ),
    ):
        try:
            direct._target_from_origin(value)
        except legacy.BootstrapStopped as exc:
            assert exc.code == direct._ORIGIN_HANDOFF_INVALID
        else:
            raise AssertionError("untrusted bootstrap destination accepted")


def test_direct_function_preflight_requires_exact_source_controlled_rejection() -> None:
    target = direct._target_from_origin(ORIGIN)
    observed: dict[str, object] = {}

    class Response:
        status = 405

        def getheader(self, name: str, default: str = "") -> str:
            if name.lower() == "content-type":
                return "application/json; charset=utf-8"
            return default

        def read(self, size: int = -1) -> bytes:
            payload = json.dumps(
                {"status": "BLOCKED", "code": "METHOD_NOT_ALLOWED"},
                separators=(",", ":"),
            ).encode("utf-8")
            return payload[:size]

    class Connection:
        def __init__(
            self,
            host: str,
            port: int,
            *,
            timeout: float,
            context: object,
        ) -> None:
            observed["host"] = host
            observed["port"] = port
            observed["timeout"] = timeout
            observed["context"] = context

        def request(
            self,
            method: str,
            path: str,
            *,
            body: bytes | None,
            headers: dict[str, str],
        ) -> None:
            observed["method"] = method
            observed["path"] = path
            observed["body"] = body
            observed["headers"] = headers

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            observed["closed"] = True

    with mock.patch.object(direct.http.client, "HTTPSConnection", Connection):
        direct._preflight_direct_function(target)

    assert observed["method"] == "GET"
    assert observed["path"] == "/"
    assert observed["body"] is None
    assert observed["headers"] == {
        "Accept": "application/json",
        "User-Agent": direct._DIRECT_USER_AGENT,
    }
    assert "Authorization" not in observed["headers"]
    assert observed["closed"] is True


def test_direct_function_preflight_blocks_provider_edge_before_oidc_mint() -> None:
    target = direct._target_from_origin(ORIGIN)

    class Response:
        status = 403

        def getheader(self, name: str, default: str = "") -> str:
            if name.lower() == "content-type":
                return "application/json"
            return default

        def read(self, size: int = -1) -> bytes:
            return b'{"provider":"untrusted"}'[:size]

    class Connection:
        def __init__(
            self,
            host: str,
            port: int,
            *,
            timeout: float,
            context: object,
        ) -> None:
            del host, port, timeout, context

        def request(
            self,
            method: str,
            path: str,
            *,
            body: bytes | None,
            headers: dict[str, str],
        ) -> None:
            assert method == "GET"
            assert path == "/"
            assert body is None
            assert "Authorization" not in headers

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    with (
        mock.patch.object(direct, "read_bootstrap_origin_handoff", return_value=target),
        mock.patch.object(direct.http.client, "HTTPSConnection", Connection),
        mock.patch.object(legacy, "_github_oidc_token") as oidc_token,
    ):
        try:
            direct.run(EXPECTED_SHA)
        except legacy.BootstrapStopped as exc:
            assert exc.code == "CLOUDFLARE_CF_D_DIRECT_HTTP_403_UNCLASSIFIED"
        else:
            raise AssertionError("provider edge rejection was accepted")
        oidc_token.assert_not_called()


def test_direct_function_request_derives_https_host_and_forwards_only_oidc() -> None:
    target = direct._target_from_origin(ORIGIN)
    oidc = _oidc_token()
    production_dsn = _production_dsn()
    observed: dict[str, object] = {}

    class Response:
        status = 200

        def getheader(self, name: str, default: str = "") -> str:
            if name.lower() == "content-type":
                return "application/json"
            return default

        def read(self, size: int = -1) -> bytes:
            payload = {
                "status": "READY",
                "runtime_role": "omni_cio_cloudflare_prod",
                "runtime_dsn": production_dsn,
                "source_sha": EXPECTED_SHA,
            }
            return json.dumps(payload).encode("utf-8")[:size]

    class Connection:
        def __init__(
            self,
            host: str,
            port: int,
            *,
            timeout: float,
            context: object,
        ) -> None:
            observed["host"] = host
            observed["port"] = port
            observed["timeout"] = timeout
            observed["context"] = context

        def request(
            self,
            method: str,
            path: str,
            *,
            body: bytes,
            headers: dict[str, str],
        ) -> None:
            observed["method"] = method
            observed["path"] = path
            observed["body"] = body
            observed["headers"] = headers

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            observed["closed"] = True

    with mock.patch.object(direct.http.client, "HTTPSConnection", Connection):
        result = direct._bootstrap_runtime_dsn_direct(target, EXPECTED_SHA, oidc)

    assert result == production_dsn
    assert observed["host"] == (
        "br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech"
    )
    assert observed["port"] == 443
    assert observed["method"] == "POST"
    assert observed["path"] == "/"
    headers = observed["headers"]
    assert isinstance(headers, dict)
    assert headers == {
        "Accept": "application/json",
        "User-Agent": direct._DIRECT_USER_AGENT,
        direct._DIRECT_OIDC_HEADER: oidc,
        "Content-Type": "application/json",
    }
    assert "Authorization" not in headers
    assert oidc not in str(observed["host"])
    context = observed["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert observed["closed"] is True


def test_direct_failure_preserves_only_bounded_unknown_http_status() -> None:
    for status in (400, 401, 403, 404, 408, 429, 500, 502, 503, 504, 530):
        assert direct._direct_failure_code(status, b"<untrusted-provider-body>") == (
            f"{direct._DIRECT_UNCLASSIFIED_HTTP_PREFIX}{status}_UNCLASSIFIED"
        )

    source_controlled = json.dumps(
        {"status": "BLOCKED", "code": "OIDC_AUDIENCE_INVALID"},
        separators=(",", ":"),
    ).encode("utf-8")
    assert direct._direct_failure_code(403, source_controlled) == (
        "CLOUDFLARE_CF_D_NEON_FUNCTION_OIDC_AUDIENCE_INVALID"
    )
    assert direct._direct_failure_code(302, b"untrusted redirect") == direct._DIRECT_REDIRECT
    assert direct._direct_failure_code(599, b"untrusted") == (
        "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_REJECTED"
    )


def test_main_candidate_hands_target_without_logging_it() -> None:
    source = CANDIDATE_RUNNER.read_text(encoding="utf-8")
    assert 'if branch == "main":' in source
    assert "write_bootstrap_origin_handoff(bootstrap_origin)" in source
    assert 'print(bootstrap_origin)' not in source
    assert "_write_output(\"bootstrap_origin\"" not in source


def test_production_release_uses_direct_function_not_public_staging_relay() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    start = source.index(
        "      - name: Reuse production database secret or bootstrap it once"
    )
    end = source.index("\n      - name:", start + 1)
    section = source[start:end]
    direct_command = (
        "python -m scripts.bootstrap_v10_cloudflare_production_database_direct"
    )
    assert direct_command in section
    assert "bootstrap_v10_cloudflare_production_database_via_staging" not in section
    assert "STAGING_ORIGIN" not in section
    assert "--origin" not in section
    assert "omni-cio-v10-cloudflare-bootstrap-origin.txt" in section


def test_direct_tls_policy_is_explicit_and_does_not_use_generic_context() -> None:
    source = Path(direct.__file__).read_text(encoding="utf-8")
    assert "ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)" in source
    assert "context.minimum_version = ssl.TLSVersion.TLSv1_2" in source
    assert "context.load_default_certs(ssl.Purpose.SERVER_AUTH)" in source
    assert "ssl.create_default_context()" not in source


def test_neon_function_preserves_legacy_authorization_and_rejects_any_dual_ingress() -> None:
    source = FUNCTION_SOURCE.read_text(encoding="utf-8")
    assert "const DIRECT_OIDC_HEADER = 'x-omni-github-oidc';" in source
    assert "request.headers.get(DIRECT_OIDC_HEADER)" in source
    assert "request.headers.get('authorization')" in source
    assert "directToken !== null && authorization !== null" in source
    assert "authorization === null || !authorization.startsWith('Bearer ')" in source
    assert "return { error: 'OIDC_HEADER_INVALID', token: '' };" in source
    assert "oidcTokenFromRequest(request)" in source


def test_direct_bootstrap_transport_is_machine_readable() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    candidate = contract["candidate"]
    cutover = contract["cutover"]
    assert (
        candidate["staging_bootstrap_origin_private_control_plane_handoff_for_main"]
        is True
    )
    assert cutover["production_database_bootstrap_active_transport"] == (
        "GITHUB_OIDC_DIRECT_NEON_FUNCTION"
    )
    assert cutover["production_database_bootstrap_public_staging_relay_active"] is False
    assert cutover["production_database_bootstrap_function_origin_custody"] == (
        "RESTRICTED_RUNNER_TEMP_TARGET_DESCRIPTOR"
    )
    assert cutover["production_database_bootstrap_function_origin_logged"] is False
    assert cutover["production_database_bootstrap_function_origin_artifacted"] is False
    assert cutover["production_database_bootstrap_target_descriptor_fields"] == [
        "branch_id",
        "cell",
    ]
    assert (
        cutover["production_database_bootstrap_target_descriptor_full_url_allowed"]
        is False
    )
    assert cutover["production_database_bootstrap_dynamic_url_handoff_allowed"] is False
    assert (
        cutover["production_database_bootstrap_tls_hostname_verification_required"]
        is True
    )
    assert cutover["production_database_bootstrap_tls_minimum_version"] == "TLSv1.2"
    assert cutover["production_database_bootstrap_function_preflight_required"] is True
    assert cutover["production_database_bootstrap_function_preflight_method"] == "GET"
    assert cutover["production_database_bootstrap_function_preflight_expected_failure"] == (
        "CLOUDFLARE_CF_D_NEON_FUNCTION_METHOD_NOT_ALLOWED"
    )
    assert cutover["production_database_bootstrap_direct_oidc_header"] == (
        direct._DIRECT_OIDC_HEADER
    )
    assert cutover["production_database_bootstrap_direct_authorization_header_allowed"] is False
    assert cutover["production_database_bootstrap_direct_ingress_preflight_required"] is True
    assert cutover["production_database_bootstrap_direct_ingress_preflight_method"] == "POST"
    assert cutover["production_database_bootstrap_direct_ingress_preflight_expected_failure"] == (
        direct._DIRECT_INGRESS_PREFLIGHT_EXPECTED_FAILURE
    )
    assert cutover["production_database_bootstrap_function_legacy_authorization_fallback_retained"] is True
    assert cutover["production_database_bootstrap_oidc_mint_after_preflight_required"] is True
    assert cutover["production_database_bootstrap_fixed_user_agent_required"] is True