"""Validate required emulator evidence; never execute a test or infer success."""
from __future__ import annotations

BASE_TESTS = frozenset({"candidate_clean_install", "activity_launch"})
UPGRADE_TESTS = frozenset({"previous_clean_install", "upgrade_to_candidate"})
PROFILE_TESTS = frozenset({"debug_ui_fixture_install", "profile_ui"})


def validate_results(results: object, *, upgrade_required: bool, profile_required: bool) -> None:
    """Accept exactly the checks requested for this run, with explicit success."""
    if not isinstance(results, list):
        raise ValueError("Invalid installation report")
    names = []
    for item in results:
        if not isinstance(item, dict) or item.get("success") is not True:
            raise ValueError("Failed or invalid installation test in report")
        name = item.get("test")
        if not isinstance(name, str):
            raise ValueError("Installation test name must be a string")
        names.append(name)
    expected = set(BASE_TESTS)
    if upgrade_required:
        expected.update(UPGRADE_TESTS)
    if profile_required:
        expected.update(PROFILE_TESTS)
    if len(names) != len(set(names)):
        raise ValueError("Duplicate installation tests")
    if set(names) != expected:
        raise ValueError("Missing or unexpected installation tests")
