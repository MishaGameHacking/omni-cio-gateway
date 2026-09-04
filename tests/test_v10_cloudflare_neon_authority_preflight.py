from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-candidate-deploy.yml"
PRODUCTION_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
NEON_PROJECT_AUTHORITY_PROBE = "probe_provider_access_from_env()"
NEON_PROVISION = "python -m scripts.provision_v10_cloudflare_neon_runtime"


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

    def test_production_neon_authority_is_conditional_on_database_bootstrap(self) -> None:
        source = self._read(PRODUCTION_WORKFLOW)
        self.assertEqual(source.count(NEON_PROJECT_AUTHORITY_PROBE), 2)
        self.assertEqual(source.count(NEON_PROVISION), 2)

        staging_secret_probe = source.index(
            "python -m scripts.probe_v10_cloudflare_staging_runtime_secret"
        )
        production_secret_probe = source.index(
            "python -m scripts.manage_v10_cloudflare_production probe-runtime-secret"
        )
        probe_indexes = [
            index
            for index in range(len(source))
            if source.startswith(NEON_PROJECT_AUTHORITY_PROBE, index)
        ]
        provision_indexes = [
            index
            for index in range(len(source))
            if source.startswith(NEON_PROVISION, index)
        ]

        self.assertEqual(len(probe_indexes), 2)
        self.assertEqual(len(provision_indexes), 2)
        self.assertLess(staging_secret_probe, probe_indexes[0])
        self.assertLess(probe_indexes[0], provision_indexes[0])
        self.assertLess(provision_indexes[0], production_secret_probe)
        self.assertLess(production_secret_probe, probe_indexes[1])
        self.assertLess(probe_indexes[1], provision_indexes[1])
        self.assertIn(
            'if [ "$neon_rc" -ne 0 ]; then',
            source[probe_indexes[0] : provision_indexes[0]],
        )
        self.assertIn(
            'if [ "$neon_rc" -ne 0 ]; then',
            source[probe_indexes[1] : provision_indexes[1]],
        )

    def test_neon_preflight_uses_only_runtime_secret_bindings(self) -> None:
        for path in (CANDIDATE_WORKFLOW, PRODUCTION_WORKFLOW):
            with self.subTest(path=path.name):
                source = self._read(path)
                probe_indexes = [
                    index
                    for index in range(len(source))
                    if source.startswith(NEON_PROJECT_AUTHORITY_PROBE, index)
                ]
                self.assertGreaterEqual(len(probe_indexes), 1)
                for probe_index in probe_indexes:
                    section_start = source.rfind("      - name:", 0, probe_index)
                    section_end = source.find("\n      - name:", probe_index)
                    self.assertGreaterEqual(section_start, 0)
                    self.assertGreater(section_end, probe_index)
                    section = source[section_start:section_end]
                    self.assertIn(
                        "NEON_API_KEY: ${{ secrets.NEON_API_KEY }}",
                        section,
                    )
                    self.assertIn(
                        "NEON_ORG_ID: ${{ secrets.NEON_ORG_ID }}",
                        section,
                    )
                    self.assertIn(
                        "NEON_PROJECT_ID: ${{ secrets.NEON_PROJECT_ID }}",
                        section,
                    )
                    self.assertNotIn("vars.NEON_", section)
                    self.assertNotIn("echo $NEON", section)


if __name__ == "__main__":
    unittest.main()
