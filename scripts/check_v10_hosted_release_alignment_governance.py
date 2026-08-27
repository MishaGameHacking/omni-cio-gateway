from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT_WORKFLOW = ROOT / ".github/workflows/v10-hosted-release-alignment.yml"
ALIGNMENT_STANDARD = ROOT / "docs/operations/V10_HOSTED_RELEASE_ALIGNMENT_STANDARD.md"
FAILURE_LEARNING = (
    ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL054.md"
)
ENGINEERING_GOVERNANCE_WORKFLOW = (
    ROOT / ".github/workflows/v10-engineering-governance.yml"
)
_REQUIRED_WORKFLOW_RUN_LISTS = {
    "workflows": {"V10 Phase 4 Free Preview Deploy"},
    "types": {"completed"},
    "branches": {"main"},
}
_EXACT_MAIN_FETCH = (
    'git fetch --no-tags --prune --depth=1 origin '
    '"+refs/heads/main:refs/remotes/origin/main"'
)


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(
            f"missing hosted-release governance file: {path.relative_to(ROOT)}"
        )
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _yaml_string_scalar(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("workflow list entry must not be empty")
    if value[0] in {"'", '"'}:
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, str):
            raise ValueError("workflow list entry must be a string")
        return parsed
    return value.split(" #", maxsplit=1)[0].rstrip()


def _yaml_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, stripped))
    return lines


def _find_key(
    lines: list[tuple[int, str]],
    key: str,
    *,
    indent: int | None = None,
) -> int:
    for index, (line_indent, stripped) in enumerate(lines):
        if stripped == key and (indent is None or line_indent == indent):
            return index
    raise ValueError(f"workflow is missing {key.rstrip(':')}")


def _child_block(
    lines: list[tuple[int, str]],
    key_index: int,
) -> list[tuple[int, str]]:
    key_indent = lines[key_index][0]
    block: list[tuple[int, str]] = []
    for line in lines[key_index + 1 :]:
        if line[0] <= key_indent:
            break
        block.append(line)
    return block


def _find_mapping_key(
    lines: list[tuple[int, str]],
    key: str,
) -> tuple[int, str]:
    prefix = f"{key}:"
    for index, (_indent, stripped) in enumerate(lines):
        if stripped.startswith(prefix):
            return index, stripped[len(prefix) :].strip()
    raise ValueError(f"workflow is missing {key}")


def _inline_list_values(raw: str) -> set[str]:
    value = raw.split(" #", maxsplit=1)[0].strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError("workflow inline list must use [value, ...] syntax")
    items = value[1:-1].strip()
    if not items:
        return set()
    return {_yaml_string_scalar(item) for item in items.split(",")}


def _list_values(block: list[tuple[int, str]], key: str) -> set[str]:
    key_index, inline = _find_mapping_key(block, key)
    if inline:
        return _inline_list_values(inline)
    values_block = _child_block(block, key_index)
    return {
        _yaml_string_scalar(stripped[1:])
        for _indent, stripped in values_block
        if stripped.startswith("-")
    }


def _workflow_run_lists(text: str) -> dict[str, set[str]]:
    lines = _yaml_lines(text)
    on_block = _child_block(lines, _find_key(lines, "on:", indent=0))
    workflow_run_block = _child_block(
        on_block,
        _find_key(on_block, "workflow_run:"),
    )
    return {
        key: _list_values(workflow_run_block, key)
        for key in _REQUIRED_WORKFLOW_RUN_LISTS
    }


def _require_markers(
    label: str,
    text: str,
    markers: tuple[str, ...],
    failures: list[str],
) -> None:
    for marker in markers:
        if marker not in text:
            failures.append(f"{label} is missing governance marker: {marker}")


def _require_minimum_occurrences(
    label: str,
    text: str,
    marker: str,
    minimum: int,
    failures: list[str],
) -> None:
    observed = text.count(marker)
    if observed < minimum:
        message = (
            f"{label} must contain {marker!r} at least {minimum} times; "
            f"observed {observed}"
        )
        failures.append(message)


def _forbid_markers(
    label: str,
    text: str,
    markers: tuple[str, ...],
    failures: list[str],
) -> None:
    for marker in markers:
        if marker in text:
            failures.append(f"{label} contains forbidden governance marker: {marker}")


def _validate_workflow_run_routing(text: str, failures: list[str]) -> None:
    try:
        observed = _workflow_run_lists(text)
    except (SyntaxError, ValueError) as exc:
        failures.append(f"hosted alignment workflow routing cannot be parsed: {exc}")
        return

    for key, expected in _REQUIRED_WORKFLOW_RUN_LISTS.items():
        if observed.get(key) != expected:
            failures.append(
                "hosted alignment workflow on.workflow_run."
                f"{key} must be {sorted(expected)!r}"
            )


def validate_sources(
    *,
    alignment_workflow: str,
    alignment_standard: str,
    failure_learning: str,
    engineering_governance_workflow: str,
    failures: list[str],
) -> None:
    _validate_workflow_run_routing(alignment_workflow, failures)
    _require_markers(
        "hosted alignment workflow",
        alignment_workflow,
        (
            "name: V10 Hosted Release Alignment",
            "schedule:",
            "actions: read",
            "contents: read",
            "cancel-in-progress: false",
            "python scripts/check_v10_exact_main_regression.py",
            "Probe canonical hosted release alignment without publishing PASS",
            "python scripts/check_v10_hosted_release_alignment.py",
            "> hosted_alignment_pass.txt",
            "Reconfirm current main before publishing runtime PASS",
            "cat hosted_alignment_pass.txt",
            "HOSTED_RELEASE_ALIGNMENT=SUPERSEDED_BY_NEWER_MAIN",
        ),
        failures,
    )
    _require_minimum_occurrences(
        "hosted alignment workflow",
        alignment_workflow,
        _EXACT_MAIN_FETCH,
        2,
        failures,
    )
    _forbid_markers(
        "hosted alignment workflow",
        alignment_workflow,
        (
            "github.event.workflow_run.conclusion",
            "RENDER_API_KEY",
            "NEON_API_KEY",
            "RENDER_ZERO_CHARGE_ATTESTATION",
        ),
        failures,
    )

    _require_markers(
        "hosted alignment standard",
        alignment_standard,
        (
            "inventory limited to `event=push` is incomplete",
            "applicable downstream `workflow_run` chain must also reach terminal state",
            "`queued`, `pending`, `in_progress`, `failure`, `cancelled`",
            "not accepted post-merge runtime evidence",
            "latest applicable alignment gate succeeds on the exact expected SHA",
            "successful probe output is withheld until a post-probe main recheck",
            "superseded older run is neither drift evidence nor current-runtime "
            "PASS evidence",
        ),
        failures,
    )

    _require_markers(
        "hosted alignment failure learning",
        failure_learning,
        (
            "Post-merge acceptance must traverse downstream deployment event topology",
            "complete applicable event chain",
            "post-probe main recheck",
            "SUPERSEDED_BY_NEWER_MAIN",
        ),
        failures,
    )

    _require_markers(
        "engineering governance workflow",
        engineering_governance_workflow,
        (
            "python scripts/check_v10_hosted_release_alignment_governance.py",
            "scripts/check_v10_hosted_release_alignment_governance.py",
            "tests.test_v10_hosted_release_alignment_governance",
        ),
        failures,
    )


def main() -> int:
    failures: list[str] = []
    alignment_workflow = _read(ALIGNMENT_WORKFLOW, failures)
    alignment_standard = _read(ALIGNMENT_STANDARD, failures)
    failure_learning = _read(FAILURE_LEARNING, failures)
    engineering_governance_workflow = _read(
        ENGINEERING_GOVERNANCE_WORKFLOW,
        failures,
    )

    validate_sources(
        alignment_workflow=alignment_workflow,
        alignment_standard=alignment_standard,
        failure_learning=failure_learning,
        engineering_governance_workflow=engineering_governance_workflow,
        failures=failures,
    )

    if failures:
        print("V10 hosted-release alignment governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 hosted-release alignment governance check passed.")
    print(
        "Post-merge downstream topology: terminal exact-main alignment SUCCESS required"
    )
    print("Runtime PASS publication: post-probe exact-main recheck required")
    print("Older superseded workflow_run: never current-runtime PASS evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
