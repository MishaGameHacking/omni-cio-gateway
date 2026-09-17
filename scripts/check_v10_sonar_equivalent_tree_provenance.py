from __future__ import annotations

from typing import Any

import scripts.check_v10_cloudflare_postmerge_release_gate as release_gate


_PULL_REQUESTS_PER_PAGE = 100
_MAX_ASSOCIATED_PULL_REQUESTS = 100
_ISSUE_EVENTS_PER_PAGE = 100
_MAX_ISSUE_EVENT_PAGES = 10
_CHECK_SUITES_PER_PAGE = 100
_MAX_FILTERED_CHECK_SUITES = 1000
_STALLED_SUITE_STATUSES = frozenset({"queued", "in_progress"})
_AUTHORITATIVE_GATE_NAME = "V10 authoritative merge gate"
_AUTHORITATIVE_GATE_APP_SLUG = "github-actions"
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


def _check_suite_page(
    repository: str,
    token: str,
    expected_sha: str,
    page: int,
) -> tuple[int, list[dict[str, Any]]]:
    payload = release_gate._api_get(  # noqa: SLF001 - same GitHub Checks authority
        f"/repos/{repository}/commits/{expected_sha}/check-suites"
        f"?per_page={_CHECK_SUITES_PER_PAGE}&page={page}",
        token,
    )
    if not isinstance(payload, dict):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITES_RESPONSE_INVALID"
        )
    total_count = payload.get("total_count")
    raw_rows = payload.get("check_suites")
    if (
        not isinstance(total_count, int)
        or total_count < 0
        or not isinstance(raw_rows, list)
    ):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITES_RESPONSE_INVALID"
        )
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITE_INVALID"
            )
        rows.append(raw)
    return total_count, rows


def _check_suites(
    repository: str,
    token: str,
    expected_sha: str,
) -> list[dict[str, Any]]:
    total_count, first_page = _check_suite_page(repository, token, expected_sha, 1)
    if total_count > _MAX_FILTERED_CHECK_SUITES:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITES_TRUNCATED"
        )
    page_count = max(
        1,
        (total_count + _CHECK_SUITES_PER_PAGE - 1) // _CHECK_SUITES_PER_PAGE,
    )
    rows = list(first_page)
    for page in range(2, page_count + 1):
        observed_total, page_rows = _check_suite_page(
            repository,
            token,
            expected_sha,
            page,
        )
        if observed_total != total_count:
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITES_CHANGED_DURING_READ"
            )
        rows.extend(page_rows)
    if len(rows) != total_count:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITES_INCOMPLETE"
        )
    if any(row.get("head_sha") != expected_sha for row in rows):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITE_FILTER_DRIFT"
        )
    return rows


def _matching_external_suites(
    rows: list[dict[str, Any]],
    required_app_slug: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for row in rows:
        app = row.get("app")
        app_slug = app.get("slug") if isinstance(app, dict) else None
        if app_slug == required_app_slug:
            matches.append(row)
    return matches


def _external_suite_ordering(row: dict[str, Any]) -> tuple[str, int]:
    suite_id = row.get("id")
    if not isinstance(suite_id, int) or isinstance(suite_id, bool) or suite_id < 1:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITE_INVALID"
        )
    timestamp = row.get("updated_at") or row.get("created_at")
    if not isinstance(timestamp, str) or not timestamp:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITE_INVALID"
        )
    return timestamp, suite_id


def _latest_external_suite(
    rows: list[dict[str, Any]],
    required_app_slug: str,
) -> dict[str, Any] | None:
    matches = _matching_external_suites(rows, required_app_slug)
    if not matches:
        return None
    return max(matches, key=_external_suite_ordering)


def _require_stalled_main_suite(
    suite: dict[str, Any],
    required_app_slug: str,
) -> int:
    app = suite.get("app")
    app_slug = app.get("slug") if isinstance(app, dict) else None
    suite_id = suite.get("id")
    check_runs_count = suite.get("latest_check_runs_count")
    if (
        app_slug != required_app_slug
        or not isinstance(suite_id, int)
        or isinstance(suite_id, bool)
        or suite_id < 1
        or suite.get("status") not in _STALLED_SUITE_STATUSES
        or suite.get("conclusion") is not None
        or check_runs_count != 0
    ):
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_SUITE_NOT_STALLED"
        )
    return suite_id


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


def _authoritative_head_gate_success(
    rows: list[dict[str, Any]],
    head_sha: str,
) -> bool:
    matches: list[dict[str, Any]] = []
    for row in rows:
        app = row.get("app")
        if (
            row.get("name") == _AUTHORITATIVE_GATE_NAME
            and row.get("head_sha") == head_sha
            and isinstance(app, dict)
            and app.get("slug") == _AUTHORITATIVE_GATE_APP_SLUG
        ):
            matches.append(row)
    if not matches:
        return False
    latest = max(
        matches,
        key=lambda row: str(row.get("completed_at") or row.get("started_at") or ""),
    )
    if latest.get("status") != "completed":
        return False
    if latest.get("conclusion") != "success":
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_AUTHORITATIVE_GATE_NOT_SUCCESS"
        )
    output = latest.get("output")
    if not isinstance(output, dict) or output.get("annotations_count") != 0:
        raise release_gate.ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_AUTHORITATIVE_GATE_ANNOTATIONS_PRESENT"
        )
    return True


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
    latest_sonar = release_gate._latest_external_check(  # noqa: SLF001
        head_checks,
        required_name,
        required_app_slug,
    )
    if latest_sonar is not None:
        if not release_gate._external_check_state(  # noqa: SLF001
            head_checks,
            required_name,
            required_app_slug,
        ):
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_CHECK_PENDING"
            )
    elif not _authoritative_head_gate_success(head_checks, head_sha):
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
    """Certify source-equivalent PR Sonar evidence for a cancelled main autoscan."""

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
    """Certify equivalent PR Sonar after bounded no-check-run evidence.

    The caller owns the bounded wait. This verifier distinguishes a genuinely absent
    Sonar suite from a provider suite that exists but is stalled with zero check-runs.
    Neither state is counted as successful provider execution; both may recover only
    through the exact same source-equivalent PR Sonar provenance after the deadline.
    """

    release_gate._require_current_main(repository, token, expected_sha)  # noqa: SLF001
    initial_suites = _check_suites(repository, token, expected_sha)
    initial_suite = _latest_external_suite(initial_suites, required_app_slug)
    initial_suite_id: int | None = None
    evidence_mode = "missing_exact_main_after_bounded_wait"
    if initial_suite is not None:
        initial_suite_id = _require_stalled_main_suite(
            initial_suite,
            required_app_slug,
        )
        evidence_mode = "stalled_exact_main_suite_after_bounded_wait"

    head_sha = _certify_equivalent_tree_pr_sonar(
        repository=repository,
        token=token,
        expected_sha=expected_sha,
        required_name=required_name,
        required_app_slug=required_app_slug,
        evidence_mode=evidence_mode,
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

    refreshed_suites = _check_suites(repository, token, expected_sha)
    refreshed_suite = _latest_external_suite(refreshed_suites, required_app_slug)
    if initial_suite_id is None:
        if refreshed_suite is not None:
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_SUITE_APPEARED"
            )
    else:
        if refreshed_suite is None:
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_SUITE_CHANGED"
            )
        refreshed_suite_id = _require_stalled_main_suite(
            refreshed_suite,
            required_app_slug,
        )
        if refreshed_suite_id != initial_suite_id:
            raise release_gate.ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_SUITE_CHANGED"
            )

    release_gate._require_current_main(repository, token, expected_sha)  # noqa: SLF001
    print(
        "CLOUDFLARE_POSTMERGE_SONAR_PROVENANCE=CERTIFIED "
        f"mode={evidence_mode} exact_main={expected_sha} "
        f"certified_head={head_sha}"
    )
    return head_sha
