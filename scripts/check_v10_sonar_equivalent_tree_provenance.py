from __future__ import annotations

from typing import Any

import scripts.check_v10_cloudflare_postmerge_release_gate as release_gate


_PULL_REQUESTS_PER_PAGE = 100
_MAX_ASSOCIATED_PULL_REQUESTS = 100


def _pull_request_page(
    repository: str,
    token: str,
    expected_sha: str,
    page: int,
) -> list[dict[str, Any]]:
    payload = release_gate._api_get(  # noqa: SLF001 - same bounded release authority
        f"/repos/{repository}/commits/{expected_sha}/pulls"
        f"?per_page={_PULL_REQUESTS_PER_PAGE}&page={page}",
        token,
    )
    if not isinstance(payload, list):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_PULLS_RESPONSE_INVALID"
        )
    rows: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_INVALID"
            )
        rows.append(raw)
    return rows


def _associated_pull_request(
    repository: str,
    token: str,
    expected_sha: str,
) -> dict[str, Any]:
    first_page = _pull_request_page(repository, token, expected_sha, 1)
    if len(first_page) >= _MAX_ASSOCIATED_PULL_REQUESTS:
        second_page = _pull_request_page(repository, token, expected_sha, 2)
        if second_page:
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_PULLS_TRUNCATED"
            )
    if len(first_page) != 1:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_NOT_UNIQUE"
        )
    return first_page[0]


def _sha_field(mapping: dict[str, Any], key: str, code: str) -> str:
    value = mapping.get(key)
    invalid_sha = (
        not isinstance(value, str)
        or release_gate._SHA.fullmatch(value.lower()) is None  # noqa: SLF001
    )
    if invalid_sha:
        raise release_gate.ReleaseGateStopped(code)
    return value.lower()


def _pull_request_head(
    pull_request: dict[str, Any],
    expected_sha: str,
) -> str:
    merged_at = pull_request.get("merged_at")
    merge_commit_sha = pull_request.get("merge_commit_sha")
    base = pull_request.get("base")
    head = pull_request.get("head")
    if not isinstance(merged_at, str) or not merged_at:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_NOT_MERGED"
        )
    if not isinstance(merge_commit_sha, str) or merge_commit_sha.lower() != expected_sha:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_MISMATCH"
        )
    if not isinstance(base, dict) or base.get("ref") != "main":
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_BASE_NOT_MAIN"
        )
    if not isinstance(head, dict):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_INVALID"
        )
    return _sha_field(
        head,
        "sha",
        "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_INVALID",
    )


def _tree_sha(repository: str, token: str, commit_sha: str) -> str:
    payload = release_gate._api_get(  # noqa: SLF001 - exact Git object provenance
        f"/repos/{repository}/git/commits/{commit_sha}",
        token,
    )
    if not isinstance(payload, dict):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_COMMIT_INVALID"
        )
    tree = payload.get("tree")
    if not isinstance(tree, dict):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_TREE_INVALID"
        )
    return _sha_field(
        tree,
        "sha",
        "CLOUDFLARE_POSTMERGE_PROVENANCE_TREE_INVALID",
    )


def _require_cancelled_main_check(main_check: dict[str, Any]) -> None:
    status_is_completed = main_check.get("status") == "completed"
    conclusion_is_cancelled = main_check.get("conclusion") == "cancelled"
    if not status_is_completed or not conclusion_is_cancelled:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_CHECK_NOT_CANCELLED"
        )
    output = main_check.get("output")
    if not isinstance(output, dict) or output.get("annotations_count") != 0:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_CHECK_ANNOTATIONS_PRESENT"
        )


def certify_cancelled_exact_main_sonar(
    *,
    repository: str,
    token: str,
    expected_sha: str,
    main_check: dict[str, Any],
    required_name: str,
    required_app_slug: str,
) -> str:
    """Certify source-equivalent PR Sonar evidence for a cancelled main autoscan.

    This is deliberately narrower than treating ``cancelled`` as GREEN. The exact-main
    check must be a clean provider cancellation, GitHub must bind the exact squash
    commit to one merged PR, both commits must reference the same Git tree, and the
    exact PR-head Sonar check must itself be a normal completed SUCCESS with zero
    findings. Any ambiguity fails closed.
    """

    release_gate._require_current_main(repository, token, expected_sha)  # noqa: SLF001
    _require_cancelled_main_check(main_check)

    pull_request = _associated_pull_request(repository, token, expected_sha)
    head_sha = _pull_request_head(pull_request, expected_sha)

    main_tree = _tree_sha(repository, token, expected_sha)
    head_tree = _tree_sha(repository, token, head_sha)
    if main_tree != head_tree:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_TREE_MISMATCH"
        )

    head_checks = release_gate._check_runs(repository, token, head_sha)  # noqa: SLF001
    if not release_gate._external_check_state(  # noqa: SLF001
        head_checks,
        required_name,
        required_app_slug,
    ):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_CHECK_MISSING"
        )

    release_gate._require_current_main(repository, token, expected_sha)  # noqa: SLF001
    print(
        "CLOUDFLARE_POSTMERGE_SONAR_PROVENANCE=CERTIFIED "
        f"exact_main={expected_sha} certified_head={head_sha} tree={main_tree}"
    )
    return head_sha
