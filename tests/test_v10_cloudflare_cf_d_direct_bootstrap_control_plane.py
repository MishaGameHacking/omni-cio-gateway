from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest import mock
from urllib.request import Request

import scripts.bootstrap_v10_cloudflare_production_database_direct as direct
import scripts.bootstrap_v10_cloudflare_production_database_via_staging as legacy


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
CANDIDATE_RUNNER = ROOT / "scripts/run_v10_cloudflare_gated_candidate.py"
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
EXPECTED_SHA = "a" * 40
OIDC = "synthetic_header.synthetic_claims.synthetic_signature"
ORIGIN = (
    "https://br-example1234-cfdprodbootstrap.compute."
    "c-6.eu-central-1.aws.neon.tech/"
)
PRODUCTION_DSN = (
    "postgresql://omni_cio_cloudflare_prod:synthetic-credential-marker@"
    "ep-example-pooler.c-6.eu-central-1.aws.neon.tech/neondb?"
    "sslmode=require&channel_binding=require"
)


def test_direct_bootstrap_origin_handoff_is_exact_private_runner_file() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with mock.patch.dict(legacy.os.environ, {"RUNNER_TEMP": str(root)}, clear=False):
            path = direct.write_bootstrap_origin_handoff(ORIGIN)
            assert path == root.resolve() / direct._BOOTSTRAP_ORIGIN_FILENAME
            assert direct.read_bootstrap_origin_handoff() == ORIGIN
            if legacy.os.name != "nt":
                assert path.stat().st_mode & 0o777 == 0o600
            direct._discard_origin_handoff(path)
            assert not path.exists()


def test_direct_bootstrap_origin_rejects_arbitrary_network_target() -> None:
    for value in (
        "https://example.com/",
        "http://br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/",
        "https://br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/path",
    ):
        try:
            direct._validated_bootstrap_origin(value)
        except legacy.BootstrapStopped as exc:
            assert exc.code == direct._ORIGIN_HANDOFF_INVALID
        else:
            raise AssertionError("untrusted bootstrap origin accepted")


def test_direct_function_request_uses_standard_oidc_only_at_function_boundary() -> None:
    observed: list[Request] = []

    def fake_request(request: Request) -> dict[str, object]:
        observed.append(request)
        return {
            "status": "READY",
            "runtime_role": "omni_cio_cloudflare_prod",
            "runtime_dsn": PRODUCTION_DSN,
            "source_sha": EXPECTED_SHA,
        }

    with mock.patch.object(direct, "_request_direct_bootstrap_json", side_effect=fake_request):
        result = direct._bootstrap_runtime_dsn_direct(ORIGIN, EXPECTED_SHA, OIDC)

    assert result == PRODUCTION_DSN
    assert len(observed) == 1
    request = observed[0]
    assert request.full_url == ORIGIN
    assert request.get_header("Authorization") == f"Bearer {OIDC}"
    assert request.get_header("X-omni-github-oidc") is None
    assert OIDC not in request.full_url


def test_main_candidate_hands_origin_to_release_control_plane_without_logging_it() -> None:
    source = CANDIDATE_RUNNER.read_text(encoding="utf-8")
    assert 'if branch == "main":' in source
    assert "write_bootstrap_origin_handoff(bootstrap_origin)" in source
    assert 'print(bootstrap_origin)' not in source
    assert "_write_output(\"bootstrap_origin\"" not in source


def test_production_release_uses_direct_function_not_public_staging_relay() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    start = source.index("      - name: Reuse production database secret or bootstrap it once")
    end = source.index("\n      - name:", start + 1)
    section = source[start:end]
    assert "python -m scripts.bootstrap_v10_cloudflare_production_database_direct" in section
    assert "bootstrap_v10_cloudflare_production_database_via_staging" not in section
    assert "STAGING_ORIGIN" not in section
    assert "--origin" not in section
    assert "omni-cio-v10-cloudflare-bootstrap-origin.txt" in section


def test_direct_bootstrap_transport_is_machine_readable() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    candidate = contract["candidate"]
    cutover = contract["cutover"]
    assert candidate["staging_bootstrap_origin_private_control_plane_handoff_for_main"] is True
    assert cutover["production_database_bootstrap_active_transport"] == (
        "GITHUB_OIDC_DIRECT_NEON_FUNCTION"
    )
    assert cutover["production_database_bootstrap_public_staging_relay_active"] is False
    assert cutover["production_database_bootstrap_function_origin_custody"] == (
        "RESTRICTED_RUNNER_TEMP"
    )
    assert cutover["production_database_bootstrap_function_origin_logged"] is False
    assert cutover["production_database_bootstrap_function_origin_artifacted"] is False
