from __future__ import annotations

from typing import Any

import scripts.check_v10_cloudflare_postmerge_release_gate as release_gate


_PULL_REQUESTS_PER_PAGE = 100
_MAX_ASSOCIATED_PULL_REQUESTS = 100
_ISSUE_EVENTS_PER_PAGE = 100
_MAX_ISSUE_EVENT_PAGES = 10
MERGE_SHA_CONVERGENCE_PENDING = (
    "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_CONVERGENCE_PENDING"
)


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


def _pull_request_number(pull_request: dict[str, Any]) -> int:
    value = pull_request.get("number")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_NUMBER_INVALID"
        )
    return value


def _canonical_pull_request(
    repository: str,
    token: str,
    associated_pull_request: dict[str, Any],
) -> dict[str, Any]:
    number = _pull_request_number(associated_pull_request)
    payload = release_gate._api_get(  # noqa: SLF001 - canonical merged-PR metadata
        f"/repos/{repository}/pulls/{number}",
        token,
    )
    if not isinstance(payload, dict):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_DETAIL_RESPONSE_INVALID"
        )
    if payload.get("number") != number:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_DETAIL_NUMBER_MISMATCH"
        )
    return payload


def _sha_value(value: Any, code: str) -> str:
    invalid_sha = (
        not isinstance(value, str) or release_gate._SHA.fullmatch(value.lower()) is None
    )  # noqa: SLF001
    if invalid_sha:
        raise release_gate.ReleaseGateStopped(code)
    return value.lower()


def _sha_field(mapping: dict[str, Any], key: str, code: str) -> str:
    return _sha_value(mapping.get(key), code)


def _issue_event_page(
    repository: str,
    token: str,
    pull_request_number: int,
    page: int,
) -> list[dict[str, Any]]:
    payload = release_gate._api_get(  # noqa: SLF001 - GitHub merge-event provenance
        f"/repos/{repository}/issues/{pull_request_number}/events"
        f"?per_page={_ISSUE_EVENTS_PER_PAGE}&page={page}",
        token,
    )
    if not isinstance(payload, list):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_RESPONSE_INVALID"
        )
    rows: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_INVALID"
            )
        rows.append(raw)
    return rows


def _merged_event_commit_sha(
    repository: str,
    token: str,
    pull_request_number: int,
) -> str:
    merged_events: list[dict[str, Any]] = []
    for page in range(1, _MAX_ISSUE_EVENT_PAGES + 1):
        rows = _issue_event_page(repository, token, pull_request_number, page)
        merged_events.extend(row for row in rows if row.get("event") == "merged")
        if len(rows) < _ISSUE_EVENTS_PER_PAGE:
            break
    else:
        overflow = _issue_event_page(
            repository,
            token,
            pull_request_number,
            _MAX_ISSUE_EVENT_PAGES + 1,
        )
        if overflow:
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_LIST_TRUNCATED"
            )

    if len(merged_events) != 1:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_NOT_UNIQUE"
        )
    return _sha_field(
        merged_events[0],
        "commit_id",
        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_COMMIT_INVALID",
    )


def _require_merge_identity(
    repository: str,
    token: str,
    pull_request_number: int,
    pull_request: dict[str, Any],
    expected_sha: str,
) -> None:
    raw_merge_sha = pull_request.get("merge_commit_sha")
    if raw_merge_sha is None:
        merged_event_sha = _merged_event_commit_sha(
            repository,
            token,
            pull_request_number,
        )
        if merged_event_sha != expected_sha:
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_COMMIT_MISMATCH"
            )
        return

    merge_sha = _sha_value(
        raw_merge_sha,
        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_INVALID",
    )
    if merge_sha != expected_sha:
        raise release_gate.ReleaseGateStopped(MERGE_SHA_CONVERGENCE_PENDING)


def _pull_request_head(pull_request: dict[str, Any]) -> str:
    merged_at = pull_request.get("merged_at")
    base = pull_request.get("base")
    head = pull_request.get("head")
    if not isinstance(merged_at, str) or not merged_at:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_NOT_MERGED"
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


def _certify_equivalent_tree_pr_sonar(
    *,
    repository: str,
    token: str,
    expected_sha: str,
    required_name: str,
    required_app_slug: str,
    evidence_mode: str,
    emit_certification: bool = True,
) -> str:
    associated_pull = _associated_pull_request(repository, token, expected_sha)
    pull_request_number = _pull_request_number(associated_pull)
    pull_request = _canonical_pull_request(repository, token, associated_pull)
    head_sha = _pull_request_head(pull_request)
    _require_merge_identity(
        repository,
        token,
        pull_request_number,
        pull_request,
        expected_sha,
    )

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
    if emit_certification:
        print(
            "CLOUDFLARE_POSTMERGE_SONAR_PROVENANCE=CERTIFIED "
            f"mode={evidence_mode} exact_main={expected_sha} "
            f"certified_head={head_sha} tree={main_tree}"
        )
    return head_sha


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

    Canonical PR merge SHA remains the primary exact-merge identity. If GitHub makes
    that field unavailable after merge, either by omitting it or returning JSON null,
    the verifier requires one bounded, unique `merged` issue event whose commit id
    equals exact main. Malformed metadata, ambiguous events and mismatches remain
    terminal; a valid non-null SHA mismatch remains pending for the outer bounded
    release loop.
    """

    release_gate._require_current_main(repository, token, expected_sha)  # noqa: SLF001
    _require_cancelled_main_check(main_check)
    return _certify_equivalent_tree_pr_sonar(
        repository=repository,
        token=token,
        expected_sha=expected_sha,
        required_name=required_name,
        required_app_slug=required_app_slug,
        evidence_mode="cancelled_exact_main",
    )


def certify_missing_exact_main_sonar(
    *,
    repository: str,
    token: str,
    expected_sha: str,
    required_name: str,
    required_app_slug: str,
) -> str:
    """Certify equivalent PR Sonar only after bounded exact-main check absence.

    The caller owns the bounded wait and proves that no matching exact-main provider
    check exists at the deadline. After source-equivalent PR evidence is collected,
    this certifier re-reads exact-main checks so a provider check that materializes
    during provenance collection cannot be bypassed by the missing-evidence path.
    """

    release_gate._require_current_main(repository, token, expected_sha)  # noqa: SLF001
    head_sha = _certify_equivalent_tree_pr_sonar(
        repository=repository,
        token=token,
        expected_sha=expected_sha,
        required_name=required_name,
        required_app_slug=required_app_slug,
        evidence_mode="missing_exact_main_after_bounded_wait",
        emit_certification=False,
    )

    refreshed_main_checks = release_gate._check_runs(  # noqa: SLF001
        repository,
        token,
        expected_sha,
    )
    if (
        release_gate._latest_external_check(  # noqa: SLF001
            refreshed_main_checks,
            required_name,
            required_app_slug,
        )
        is not None
    ):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_CHECK_APPEARED"
        )

    release_gate._require_current_main(repository, token, expected_sha)  # noqa: SLF001
    print(
        "CLOUDFLARE_POSTMERGE_SONAR_PROVENANCE=CERTIFIED "
        "mode=missing_exact_main_after_bounded_wait "
        f"exact_main={expected_sha} certified_head={head_sha}"
    )
    return head_sha
