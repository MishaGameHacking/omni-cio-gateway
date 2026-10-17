"""Validate required emulator evidence; never execute a test or infer success."""
from __future__ import annotations

from pathlib import Path
import sys

BASE_TESTS = frozenset({"candidate_clean_install", "bootstrap_activity_launch"})
UPGRADE_TESTS = frozenset({
    "previous_clean_install",
    "upgrade_to_candidate",
    "upgrade_bootstrap_launch",
})
PROFILE_TESTS = frozenset({"debug_ui_fixture_install", "profile_ui"})


def validate_current_ui(profile: dict, fixture: dict) -> None:
    # Reuse the publication parser's exact current matrix. Import only the local
    # pure evidence module; this check never initializes a backend or network.
    checkout = str(Path(__file__).resolve().parents[2])
    if checkout not in sys.path:
        sys.path.insert(0, checkout)
    from backend.installation_evidence import validate_business_receipt
    validate_business_receipt(profile, fixture.get("apk_sha256"))


def validate_results(results: object, *, upgrade_required: bool, profile_required: bool,
                     android_api: int | None = None) -> None:
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
    if android_api is not None:
        from kernel_page_size import TEST_NAME, validate_record
        expected.add(TEST_NAME)
    if len(names) != len(set(names)):
        raise ValueError("Duplicate installation tests")
    if set(names) != expected:
        raise ValueError("Missing or unexpected installation tests")
    if android_api is not None:
        validate_record(next(item for item in results if item["test"] == TEST_NAME), android_api)
        if profile_required:
            validate_current_ui(next(item for item in results if item["test"] == "profile_ui"),
                                next(item for item in results if item["test"] == "debug_ui_fixture_install"))
