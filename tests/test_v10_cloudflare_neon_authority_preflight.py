from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
READINESS_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-provider-readiness.yml"
CANDIDATE_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-candidate-deploy.yml"
PRODUCTION_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
NEON_PROJECT_AUTHORITY_PROBE = (
    "python -m scripts.resolve_v10_neon_github_integration probe"
)
NEON_DIAGNOSTIC = "python -m scripts.resolve_v10_neon_github_integration diagnose"


class CloudflareNeonAuthorityPreflightTests(unittest.TestCase):
    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _assert_probe_precedes(self, source: str, markers: tuple[str, ...]) -> None:
        self.assertEqual(source.count(NEON_PROJECT_AUTHORITY_PROBE), 1)
        probe_index = source.index(NEON_PROJECT_AUTHORITY_PROBE)
        for marker in markers:
            with self.subTest(marker=marker):
                marker_index = source.index(marker)
                self.assertLess(probe_index, marker_index)

    def _assert_neon_integration_custody(self, source: str) -> None:
        self.assertIn("NEON_API_KEY: ${{ secrets.NEON_API_KEY }}", source)
        self.assertIn("NEON_ORG_ID: ${{ secrets.NEON_ORG_ID }}", source)
        self.assertNotIn("NEON_PROJECT_ID:", source)
        self.assertNotIn("NEON_PROJECT_ID_VALUE:", source)
        self.assertNotIn("secrets.NEON_PROJECT_ID", source)
        self.assertNotIn("vars.NEON_PROJECT_ID", source)
        self.assertNotIn("echo $NEON", source)

    def test_candidate_neon_authority_is_read_before_provider_mutation(self) -> None:
        source = self._read(CANDIDATE_WORKFLOW)
        self._assert_probe_precedes(
            source,
            (
                "- name: Quarantine stale automatic staging trigger",
                "- name: Install exact Cloudflare delivery toolchain",
                "- name: Provision isolated Neon staging runtime role",
                "- name: Bootstrap isolated staging Worker without local Containers",
                "- name: Configure Workers Builds and accept exact staging build",
            ),
        )

    def test_production_neon_authority_is_read_before_release_work(self) -> None:
        source = self._read(PRODUCTION_WORKFLOW)
        self._assert_probe_precedes(
            source,
            (
                "- name: Install exact Cloudflare delivery toolchain",
                "- name: Rehearse exact accepted main on isolated staging Worker and Container",
                "- name: Bootstrap production Worker anchor without public route if absent",
                "- name: Reuse production database secret or bootstrap it once",
                "- name: Deploy exact accepted main through gated Cloudflare Workers Build",
            ),
        )

    def test_release_workflows_never_render_project_identifier_context(self) -> None:
        for path in (CANDIDATE_WORKFLOW, PRODUCTION_WORKFLOW):
            with self.subTest(path=path.name):
                source = self._read(path)
                self._assert_neon_integration_custody(source)
                self.assertEqual(source.count(NEON_DIAGNOSTIC), 1)
                self.assertIn(
                    "python -m scripts.resolve_v10_neon_github_integration provision",
                    source,
                )

    def test_provider_readiness_never_renders_project_identifier_context(self) -> None:
        source = self._read(READINESS_WORKFLOW)
        self._assert_neon_integration_custody(source)
        self.assertIn("NEON_API_KEY_VALUE: ${{ secrets.NEON_API_KEY }}", source)
        self.assertIn("NEON_ORG_ID_VALUE: ${{ secrets.NEON_ORG_ID }}", source)
        self.assertEqual(source.count(NEON_PROJECT_AUTHORITY_PROBE), 1)
        self.assertEqual(source.count(NEON_DIAGNOSTIC), 1)


if __name__ == "__main__":
    unittest.main()
