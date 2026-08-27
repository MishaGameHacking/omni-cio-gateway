from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v10-phase4-free-preview-deploy.yml"
MODULE = "scripts.provision_v10_render_neon_preview_org_scope"
LEGACY_MODULE = "scripts.provision_v10_render_neon_preview"


def _clean_python_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def test_phase4_workflow_executes_org_scoped_adapter_as_repo_root_module() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert f"python -m {MODULE}" in text
    assert f"python -m {LEGACY_MODULE} \\\n" not in text
    assert "python scripts/provision_v10_render_neon_preview.py" not in text
    assert "tests/test_wp22a_phase4_provisioner_import_path.py" in text


def test_phase4_module_invocation_is_resolvable_without_pythonpath() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", MODULE, "--help"],
        cwd=ROOT,
        env=_clean_python_env(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--expected-sha" in completed.stdout
    assert "--repo-root" in completed.stdout


def test_phase4_bootstrap_import_closure_resolves_from_repo_root() -> None:
    code = "\n".join(
        [
            "from psycopg import sql",
            "from omni_cio.persistence.hosted_postgres_runtime_v1 import (",
            "    load_hosted_postgres_runtime_contract,",
            "    validate_hosted_postgres_runtime_sql,",
            ")",
            "from omni_cio.persistence.migration import apply_migrations",
            "del sql, load_hosted_postgres_runtime_contract, validate_hosted_postgres_runtime_sql, apply_migrations",
            "print('PHASE4_BOOTSTRAP_IMPORTS=PASS')",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=_clean_python_env(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "PHASE4_BOOTSTRAP_IMPORTS=PASS"
