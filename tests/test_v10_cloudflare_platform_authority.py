from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_cloudflare_platform_authority.py"
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json"
SPEC = importlib.util.spec_from_file_location("cloudflare_platform_authority", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _failures(payload: dict[str, object]) -> list[str]:
    failures: list[str] = []
    checker.validate_contract(payload, failures)
    return failures


def test_current_repository_satisfies_cloudflare_authority() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "GitHub rank 1; Cloudflare Workers Paid platform rank 2" in completed.stdout
    assert "Legacy Render new-V10 deployment/alignment: retired" in completed.stdout
    assert "Next stage: CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION" in completed.stdout


def test_contract_rejects_render_or_cloudru_reactivation() -> None:
    payload = _contract()
    provider = payload["provider_transition"]
    assert isinstance(provider, dict)
    provider["render_new_v10_target_selected"] = True
    provider["cloudru_new_v10_target_selected"] = True

    failures = _failures(payload)

    assert "provider.render_new_v10_target_selected must be False" in failures
    assert "provider.cloudru_new_v10_target_selected must be False" in failures


def test_contract_rejects_merge_to_immediate_production() -> None:
    payload = _contract()
    release = payload["continuous_release"]
    assert isinstance(release, dict)
    release["merge_immediately_deploys_production"] = True

    failures = _failures(payload)

    assert "continuous_release.merge_immediately_deploys_production must be False" in failures


def test_contract_rejects_superseded_candidate_promotion() -> None:
    payload = _contract()
    release = payload["continuous_release"]
    assert isinstance(release, dict)
    release["superseded_candidate_may_be_promoted"] = True

    failures = _failures(payload)

    assert "continuous_release.superseded_candidate_may_be_promoted must be False" in failures


def test_contract_rejects_unapproved_paid_overage() -> None:
    payload = _contract()
    builds = payload["workers_builds"]
    assert isinstance(builds, dict)
    builds["automatic_paid_overage_beyond_authorized_baseline_allowed"] = True

    failures = _failures(payload)

    assert (
        "workers_builds.automatic_paid_overage_beyond_authorized_baseline_allowed must be False"
        in failures
    )


def test_contract_rejects_stale_paid_build_reference() -> None:
    payload = _contract()
    builds = payload["workers_builds"]
    assert isinstance(builds, dict)
    builds["concurrent_builds_per_account_reference"] = 7

    failures = _failures(payload)

    assert "workers_builds.concurrent_builds_per_account_reference must be 6" in failures


def test_contract_rejects_hyperdrive_pg18_assumption() -> None:
    payload = _contract()
    database = payload["database"]
    assert isinstance(database, dict)
    database["hyperdrive_postgresql18_assumed_supported"] = True
    database["hyperdrive_pg18_compatibility_test_required"] = False

    failures = _failures(payload)

    assert "database.hyperdrive_postgresql18_assumed_supported must be False" in failures
    assert "database.hyperdrive_pg18_compatibility_test_required must be True" in failures


def test_contract_rejects_cloudflare_product_identity_widening() -> None:
    payload = _contract()
    product = payload["product"]
    security = payload["security"]
    assert isinstance(product, dict)
    assert isinstance(security, dict)
    product["cloudflare_is_product_identity"] = True
    security["access_replaces_product_authentication"] = True

    failures = _failures(payload)

    assert "product.cloudflare_is_product_identity must be False" in failures
    assert "security.access_replaces_product_authentication must be False" in failures


def test_contract_rejects_public_or_broker_authority_widening() -> None:
    payload = _contract()
    protected = payload["protected_invariants"]
    assert isinstance(protected, dict)
    protected["public_multi_user_enabled"] = True
    protected["broker_write_enabled"] = True
    protected["real_trading_enabled"] = True

    failures = _failures(payload)

    assert "protected_invariants.public_multi_user_enabled must be False" in failures
    assert "protected_invariants.broker_write_enabled must be False" in failures
    assert "protected_invariants.real_trading_enabled must be False" in failures


def test_contract_rejects_implementation_sequence_reordering() -> None:
    payload = _contract()
    sequence = payload["implementation_sequence"]
    assert isinstance(sequence, list)
    sequence[0], sequence[1] = sequence[1], sequence[0]

    failures = _failures(payload)

    assert any("Cloudflare implementation sequence must remain" in item for item in failures)


def test_contract_rejects_provider_mutation_in_first_two_stages() -> None:
    payload = _contract()
    sequence = payload["implementation_sequence"]
    assert isinstance(sequence, list)
    first = sequence[0]
    assert isinstance(first, dict)
    first["provider_mutation"] = True

    failures = _failures(payload)

    assert "first two Cloudflare stages must not mutate provider state" in failures


def test_repository_validator_rejects_reactivated_render_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase4 = tmp_path / "phase4.yml"
    phase4.write_text(
        "name: V10 Phase 4 Free Preview Deploy\n"
        "on:\n"
        "  workflow_run:\n"
        "  workflow_dispatch:\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  retired:\n"
        "    runs-on: [self-hosted, Windows, X64, omni-cio-ci]\n"
        "    steps:\n"
        "      - run: |\n"
        "          echo LEGACY_RENDER_PHASE4_RETIRED_AMENDMENT_14\n"
        "          exit /b 78\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(checker, "PHASE4_WORKFLOW", phase4)
    failures: list[str] = []

    checker.validate_repository(failures)

    assert any("reactivated forbidden marker: workflow_run:" in item for item in failures)
