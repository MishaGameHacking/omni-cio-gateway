from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json"
)
PROVENANCE = ROOT / "scripts/check_v10_sonar_equivalent_tree_provenance.py"
PRODUCTION_RELEASE = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"


def test_null_merge_sha_fallback_is_frozen_fail_closed() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    sonar = payload["sonar_review"]
    assert (
        sonar["post_merge_cancelled_fallback_merge_sha_must_equal_exact_main"]
        is True
    )
    assert (
        sonar["post_merge_cancelled_fallback_valid_merge_sha_mismatch_state"]
        == "PENDING"
    )
    assert sonar["post_merge_cancelled_fallback_null_merge_sha_is_not_success"] is True
    assert (
        sonar["post_merge_cancelled_fallback_null_merge_sha_requires_unique_merged_event"]
        is True
    )
    assert (
        sonar["post_merge_cancelled_fallback_merged_event_commit_must_equal_exact_main"]
        is True
    )
    assert (
        sonar["post_merge_cancelled_fallback_missing_merge_sha_key_terminal"] is True
    )
    assert (
        sonar["post_merge_cancelled_fallback_merge_event_pagination_bounded"] is True
    )


def test_null_merge_sha_guard_and_workflow_permission_are_permanent() -> None:
    source = PROVENANCE.read_text(encoding="utf-8")
    workflow = PRODUCTION_RELEASE.read_text(encoding="utf-8")
    for marker in (
        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_MISSING",
        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_NOT_UNIQUE",
        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_COMMIT_INVALID",
        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_COMMIT_MISMATCH",
        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_LIST_TRUNCATED",
        "/issues/{pull_request_number}/events",
    ):
        assert marker in source
    assert "pull-requests: read" in workflow
