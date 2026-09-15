from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import scripts.check_v10_provider_secret_custody as guard


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("docs/architecture/V10_PROVIDER_SECRET_CUSTODY_CONTRACT.json")
PROVIDER_WORKFLOW = Path(".github/workflows/v10-cloudflare-provider-readiness.yml")
PRODUCTION_WORKFLOW = Path(".github/workflows/v10-cloudflare-production-release.yml")
RETIRED_HOSTED_WORKFLOW = Path(".github/workflows/v10-hosted-release-alignment.yml")
RETIRED_PREVIEW_WORKFLOW = Path(".github/workflows/v10-phase4-free-preview-deploy.yml")


def _fixture(parent: Path) -> Path:
    root = parent / "repo"
    (root / ".github/workflows").mkdir(parents=True)
    (root / CONTRACT_PATH.parent).mkdir(parents=True)
    shutil.copy2(ROOT / CONTRACT_PATH, root / CONTRACT_PATH)

    active: dict[str, list[str]] = json.loads(
        (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
    )["active_workflows"]
    for relative, names in active.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        env_lines = "\n".join(
            f"          {name}: ${{{{ secrets.{name} }}}}" for name in names
        )
        path.write_text(
            "name: fixture\njobs:\n  fixture:\n    runs-on: test\n    steps:\n"
            "      - name: bounded\n        env:\n"
            f"{env_lines}\n        run: echo guarded\n",
            encoding="utf-8",
        )

    for relative in (RETIRED_HOSTED_WORKFLOW, RETIRED_PREVIEW_WORKFLOW):
        (root / relative).write_text(
            "name: retired\njobs:\n  retired:\n    runs-on: test\n    steps:\n"
            "      - run: exit 79\n",
            encoding="utf-8",
        )
    return root


def _append(root: Path, relative: Path, text: str) -> None:
    target = root / relative
    target.write_text(target.read_text(encoding="utf-8") + text, encoding="utf-8")


def _replace(root: Path, relative: Path, old: str, new: str) -> None:
    target = root / relative
    source = target.read_text(encoding="utf-8")
    target.write_text(source.replace(old, new, 1), encoding="utf-8")


class ProviderSecretCustodyTests(unittest.TestCase):
    def _root(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return _fixture(Path(temporary.name))

    def _assert_rejected(self, root: Path, code: str) -> None:
        with self.assertRaisesRegex(RuntimeError, code):
            guard.validate(root)

    def test_minimal_contract_fixture_passes(self) -> None:
        guard.validate(self._root())

    def test_repository_provider_secret_custody_contract_passes(self) -> None:
        guard.validate(ROOT)

    def test_unknown_workflow_secret_is_rejected(self) -> None:
        root = self._root()
        _append(
            root,
            PROVIDER_WORKFLOW,
            "\n# ${{ secrets.UNREVIEWED_PROVIDER_SECRET }}\n",
        )
        self._assert_rejected(
            root,
            "PROVIDER_SECRET_CUSTODY_UNREVIEWED_SECRET_REFERENCED",
        )

    def test_retired_render_secret_is_rejected(self) -> None:
        root = self._root()
        _append(root, RETIRED_HOSTED_WORKFLOW, "\n# ${{ secrets.RENDER_API_KEY }}\n")
        self._assert_rejected(
            root,
            "PROVIDER_SECRET_CUSTODY_DEPRECATED_SECRET_REFERENCED",
        )

    def test_removed_function_invoke_secret_is_rejected(self) -> None:
        root = self._root()
        _append(
            root,
            PRODUCTION_WORKFLOW,
            "\n# ${{ secrets.NEON_FUNCTION_INVOKE_API_TOKEN }}\n",
        )
        self._assert_rejected(
            root,
            "PROVIDER_SECRET_CUSTODY_DEPRECATED_SECRET_REFERENCED",
        )

    def test_dormant_function_deploy_key_cannot_enter_active_workflow(self) -> None:
        root = self._root()
        _append(
            root,
            PRODUCTION_WORKFLOW,
            "\n# ${{ secrets.NEON_FUNCTION_DEPLOY_API_KEY }}\n",
        )
        self._assert_rejected(
            root,
            "PROVIDER_SECRET_CUSTODY_ACTIVE_BINDINGS_MISMATCH",
        )

    def test_protected_identifier_variable_fallback_is_rejected(self) -> None:
        root = self._root()
        _append(root, PROVIDER_WORKFLOW, "\n# ${{ vars.NEON_PROJECT_ID }}\n")
        self._assert_rejected(
            root,
            "PROVIDER_SECRET_CUSTODY_VARIABLE_FALLBACK_FORBIDDEN",
        )

    def test_job_level_secret_injection_is_rejected(self) -> None:
        root = self._root()
        _replace(
            root,
            PROVIDER_WORKFLOW,
            "    steps:\n",
            "    env:\n      BAD: ${{ secrets.NEON_API_KEY }}\n    steps:\n",
        )
        self._assert_rejected(root, "PROVIDER_SECRET_CUSTODY_JOB_SCOPE_TOO_BROAD")

    def test_missing_production_domain_binding_is_rejected(self) -> None:
        root = self._root()
        _replace(
            root,
            PRODUCTION_WORKFLOW,
            "          CLOUDFLARE_ZONE_ID: ${{ secrets.CLOUDFLARE_ZONE_ID }}\n",
            "",
        )
        self._assert_rejected(
            root,
            "PROVIDER_SECRET_CUSTODY_ACTIVE_BINDINGS_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
