from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PHASE4 = ROOT / ".github/workflows/v10-wp22a-phase4-public-acceptance.yml"
PHASE5 = ROOT / ".github/workflows/v10-wp22a-phase5-technical-closeout.yml"


def _pull_request_paths(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    block = text.split("    paths:\n", maxsplit=1)[1].split(
        "\n\npermissions:", maxsplit=1
    )[0]
    return {
        line.removeprefix('      - "').removesuffix('"')
        for line in block.splitlines()
        if line.startswith('      - "')
    }


class HistoricalWP22AGateRoutingTests(unittest.TestCase):
    def test_phase4_one_shot_gate_ignores_live_status_changes(self) -> None:
        assert _pull_request_paths(PHASE4) == {
            "docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.json",
            "docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md",
        }

    def test_phase5_one_shot_gate_ignores_live_status_changes(self) -> None:
        assert _pull_request_paths(PHASE5) == {
            "docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json",
            "docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.json",
            "docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.md",
        }


if __name__ == "__main__":
    unittest.main()
