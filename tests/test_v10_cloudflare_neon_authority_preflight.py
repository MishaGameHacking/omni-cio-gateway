from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-candidate-deploy.yml"
PRODUCTION_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
NEON_PROJECT_AUTHORITY_PROBE = "probe_provider_access_from_env()"


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

    def test_neon_preflight_uses_only_runtime_secret_bindings(self) -> None:
        for path in (CANDIDATE_WORKFLOW, PRODUCTION_WORKFLOW):
            with self.subTest(path=path.name):
                source = self._read(path)
                probe_index = source.index(NEON_PROJECT_AUTHORITY_PROBE)
                section_start = source.rfind("      - name:", 0, probe_index)
                section_end = source.find("\n      - name:", probe_index)
                self.assertGreaterEqual(section_start, 0)
                self.assertGreater(section_end, probe_index)
                section = source[section_start:section_end]
                self.assertIn("NEON_API_KEY: ${{ secrets.NEON_API_KEY }}", section)
                self.assertIn("NEON_ORG_ID: ${{ secrets.NEON_ORG_ID }}", section)
                self.assertIn("NEON_PROJECT_ID: ${{ secrets.NEON_PROJECT_ID }}", section)
                self.assertNotIn("vars.NEON_", section)
                self.assertNotIn("echo $NEON", section)


if __name__ == "__main__":
    unittest.main()
