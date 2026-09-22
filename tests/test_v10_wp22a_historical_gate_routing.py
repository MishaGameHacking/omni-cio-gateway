from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PHASE4 = ROOT / ".github/workflows/v10-wp22a-phase4-public-acceptance.yml"
PHASE5 = ROOT / ".github/workflows/v10-wp22a-phase5-technical-closeout.yml"


def _yaml_string_scalar(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise AssertionError("workflow path entry must not be empty")
    if value[0] in {"'", '"'}:
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, str):
            raise AssertionError("workflow path entry must be a string")
        return parsed
    return value.split(" #", maxsplit=1)[0].rstrip()


def _pull_request_paths_from_text(text: str) -> set[str]:
    on_indent: int | None = None
    pull_request_indent: int | None = None
    paths_indent: int | None = None
    paths: set[str] = set()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if stripped == "on:" and indent == 0:
            on_indent = indent
            continue
        if on_indent is None:
            continue
        if indent <= on_indent:
            break

        if stripped == "pull_request:":
            pull_request_indent = indent
            continue
        if pull_request_indent is None:
            continue
        if indent <= pull_request_indent:
            break

        if stripped == "paths:":
            paths_indent = indent
            continue
        if paths_indent is None:
            continue
        if indent <= paths_indent:
            break
        if stripped.startswith("-"):
            paths.add(_yaml_string_scalar(stripped[1:]))

    if paths_indent is None:
        raise AssertionError("workflow is missing on.pull_request.paths")
    return paths


def _pull_request_paths(path: Path) -> set[str]:
    return _pull_request_paths_from_text(path.read_text(encoding="utf-8"))


class HistoricalWP22AGateRoutingTests(unittest.TestCase):
    def test_parser_tolerates_benign_yaml_formatting_changes(self) -> None:
        workflow = """
on:
  workflow_dispatch:
  pull_request:
    types: [opened, synchronize]

    paths:
      - 'docs/alpha.md'
      - docs/beta/*.json
      - "docs/gamma.yml"

permissions:
  contents: read
"""
        assert _pull_request_paths_from_text(workflow) == {
            "docs/alpha.md",
            "docs/beta/*.json",
            "docs/gamma.yml",
        }

    def _assert_retired_archive(self, path: Path) -> None:
        source = path.read_text(encoding="utf-8")
        assert "ARCHIVE-IN-PLACE" in source
        assert "\n  workflow_dispatch:" in source
        assert "\n  pull_request:" not in source
        assert "\n  push:" not in source
        assert "\n  workflow_run:" not in source
        assert "\n  schedule:" not in source
        assert "\n  workflow_call:" not in source
        assert "if: $" + "{{ false }}" in source

    def test_phase4_one_shot_gate_is_archive_only(self) -> None:
        self._assert_retired_archive(PHASE4)

    def test_phase5_one_shot_gate_is_archive_only(self) -> None:
        self._assert_retired_archive(PHASE5)


if __name__ == "__main__":
    unittest.main()
