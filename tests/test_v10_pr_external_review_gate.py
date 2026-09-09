from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_pr_external_review_gate.py"
SPEC = importlib.util.spec_from_file_location("v10_external_review_gate", SCRIPT)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class V10ExternalReviewGateTests(unittest.TestCase):
    def _run(
        self,
        *,
        sha: str = "a" * 40,
        status: str = "completed",
        conclusion: str = "success",
        issues: int = 0,
        hotspots: int = 0,
        annotations: int = 0,
    ) -> dict[str, object]:
        return {
            "name": MODULE.SONAR_CHECK_NAME,
            "head_sha": sha,
            "status": status,
            "conclusion": conclusion,
            "started_at": "2026-09-08T20:00:00Z",
            "completed_at": "2026-09-08T20:01:00Z" if status == "completed" else None,
            "output": {
                "summary": (
                    f"[Quality Gate](https://sonarcloud.io/)  "
                    f"[{issues} New issues](https://sonarcloud.io/)  "
                    f"[{hotspots} Security Hotspots](https://sonarcloud.io/)"
                ),
                "annotations_count": annotations,
                "annotations_url": (
                    "https://api.github.com/repos/owner/repo/check-runs/1/annotations"
                ),
            },
        }

    def test_exact_clean_sonar_run_passes(self) -> None:
        assert MODULE._validate_sonar_run(self._run()) == []

    def test_nonzero_new_issues_fail_closed(self) -> None:
        failures = MODULE._validate_sonar_run(self._run(issues=5, annotations=5))
        assert any("new issues must be 0" in item for item in failures)
        assert any("annotations/new findings must be 0" in item for item in failures)

    def test_nonzero_hotspots_fail_closed(self) -> None:
        failures = MODULE._validate_sonar_run(self._run(hotspots=1))
        assert any("Security Hotspots must be 0" in item for item in failures)

    def test_incomplete_or_failed_quality_gate_fails_closed(self) -> None:
        incomplete = MODULE._validate_sonar_run(
            self._run(status="in_progress", conclusion="success")
        )
        failed = MODULE._validate_sonar_run(self._run(conclusion="failure"))
        assert any("not completed" in item for item in incomplete)
        assert any("Quality Gate is not success" in item for item in failed)

    def test_missing_summary_metrics_fail_closed(self) -> None:
        run = self._run()
        output = run["output"]
        assert isinstance(output, dict)
        output["summary"] = "Quality Gate passed"
        failures = MODULE._validate_sonar_run(run)
        assert any("new-issues metric" in item for item in failures)
        assert any("Security-Hotspots metric" in item for item in failures)

    def test_only_exact_head_sonar_run_is_selected(self) -> None:
        exact_sha = "b" * 40
        payload = {
            "check_runs": [
                self._run(sha="a" * 40),
                self._run(sha=exact_sha),
            ]
        }
        selected = MODULE._find_exact_sonar_run(payload, exact_sha)
        assert selected is not None
        assert selected["head_sha"] == exact_sha

    def test_wrong_head_does_not_satisfy_gate(self) -> None:
        payload = {"check_runs": [self._run(sha="a" * 40)]}
        assert MODULE._find_exact_sonar_run(payload, "b" * 40) is None


if __name__ == "__main__":
    unittest.main()
