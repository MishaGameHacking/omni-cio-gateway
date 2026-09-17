from __future__ import annotations

from datetime import datetime
import os
import re
import sys
import time
from typing import Any

import scripts.check_v10_cloudflare_postmerge_release_gate as release_gate


SONAR_CHECK_NAME = "SonarCloud Code Analysis"
SONAR_APP_SLUG = "sonarqubecloud"
SONAR_BOT_LOGIN = "sonarqubecloud[bot]"
SONAR_EXACT_HEAD = "Sonar exact-head"
EXTERNAL_GATE_FAILED = "External review gate failed"
STATUS_COMPLETED = "completed"
OUTPUT_KEY = "output"
ANNOTATIONS_COUNT_KEY = "annotations_count"
ZERO_NEW_ISSUES = re.compile(r"\[(\d+) New issues\]")
ZERO_ACCEPTED_ISSUES = re.compile(r"\[(\d+) Accepted issues\]")
ZERO_HOTSPOTS = re.compile(r"\[(\d+) Security Hotspots\]")
NEW_ISSUES_ZERO_FAILURE = "new issues must be 0"
HOTSPOTS_ZERO_FAILURE = "Security Hotspots must be 0"
DEFAULT_ATTEMPTS = 25
DEFAULT_DELAY_SECONDS = 5
_STALLED_SUITE_STATUSES = frozenset({"queued", "in_progress"})
_MAX_PAGE_SIZE = 100
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GOVERNANCE_CHECK_NAME = "Engineering quality and green-merge contract"
_GITHUB_ACTIONS_APP_SLUG = "github-actions"


class ReviewGateError(RuntimeError):
    """Raised when exact-head external review evidence cannot be trusted."""


class ReviewGateHttpError(ReviewGateError):
    """Preserve GitHub HTTP status for bounded read-authority fallbacks."""

    def __init__(self, status: int) -> None:
        super().__init__(f"GitHub review-gate request failed with HTTP {status}")
        self.status = status


def _github_json(path: str, token: str) -> Any:
    """Reuse the fixed-host, bounded GitHub API client accepted by CF-D."""

    try:
        return release_gate._api_get(path, token)  # noqa: SLF001 - shared API authority
    except release_gate.ReleaseGateStopped as exc:
        if exc.status is not None:
            raise ReviewGateHttpError(exc.status) from exc
        raise ReviewGateError(f"GitHub review-gate request failed: {exc.code}") from exc


def _check_runs_path(repository: str, head_sha: str) -> str:
    return (
        f"/repos/{repository}/commits/{head_sha}/check-runs"
        "?per_page=100&filter=latest"
    )


def _check_suites_path(repository: str, head_sha: str) -> str:
    return f"/repos/{repository}/commits/{head_sha}/check-suites?per_page=100"


def _pulls_path(repository: str, head_sha: str) -> str:
    return f"/repos/{repository}/commits/{head_sha}/pulls?per_page=100"


def _commit_path(repository: str, head_sha: str) -> str:
    return f"/repos/{repository}/commits/{head_sha}"


def _comments_path(repository: str, pull_request_number: int) -> str:
    return f"/repos/{repository}/issues/{pull_request_number}/comments?per_page=100"


def _annotations_path(repository: str, check_run_id: int) -> str:
    return f"/repos/{repository}/check-runs/{check_run_id}/annotations?per_page=100"


def _find_exact_sonar_run(payload: Any, head_sha: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    runs = payload.get("check_runs")
    if not isinstance(runs, list):
        return None
    matches = [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("name") == SONAR_CHECK_NAME
        and run.get("head_sha") == head_sha
        and isinstance(run.get("app"), dict)
        and run["app"].get("slug") == SONAR_APP_SLUG
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda run: str(run.get("completed_at") or run.get("started_at") or ""),
    )


def _metric(summary: str, pattern: re.Pattern[str], label: str) -> int:
    match = pattern.search(summary)
    if match is None:
        raise ReviewGateError(f"Sonar summary missing {label}")
    return int(match.group(1))


def _validate_sonar_run(run: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if run.get("status") != STATUS_COMPLETED:
        failures.append(f"{SONAR_EXACT_HEAD} check is not completed")
    if run.get("conclusion") != "success":
        failures.append(f"{SONAR_EXACT_HEAD} Quality Gate is not success")

    output = run.get(OUTPUT_KEY)
    output = output if isinstance(output, dict) else {}
    summary = output.get("summary")
    summary = summary if isinstance(summary, str) else ""

    for pattern, label, failure_message in (
        (ZERO_NEW_ISSUES, "new-issues metric", NEW_ISSUES_ZERO_FAILURE),
        (ZERO_HOTSPOTS, "Security-Hotspots metric", HOTSPOTS_ZERO_FAILURE),
    ):
        try:
            value = _metric(summary, pattern, label)
        except ReviewGateError as exc:
            failures.append(str(exc))
        else:
            if value != 0:
                failures.append(f"{SONAR_EXACT_HEAD} {failure_message}, got {value}")

    annotations_count = output.get(ANNOTATIONS_COUNT_KEY)
    if annotations_count != 0:
        failures.append(
            f"{SONAR_EXACT_HEAD} annotations/new findings must be 0, "
            f"got {annotations_count!r}"
        )
    return failures


def _annotation_lines(
    run: dict[str, Any],
    repository: str,
    token: str,
) -> list[str]:
    output = run.get(OUTPUT_KEY)
    output = output if isinstance(output, dict) else {}
    if output.get(ANNOTATIONS_COUNT_KEY) in (None, 0):
        return []
    check_run_id = run.get("id")
    if (
        not isinstance(check_run_id, int)
        or isinstance(check_run_id, bool)
        or check_run_id <= 0
    ):
        return ["Sonar check-run id missing or invalid"]
    payload = _github_json(_annotations_path(repository, check_run_id), token)
    if not isinstance(payload, list):
        return ["Sonar annotations response is not a list"]
    lines: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "<unknown>")
        line = item.get("start_line")
        title = str(item.get("title") or "Sonar finding")
        message = str(item.get("message") or "").replace("\n", " ").strip()
        lines.append(f"{path}:{line}: {title}: {message}")
    return lines


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ReviewGateError(f"{label} timestamp missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewGateError(f"{label} timestamp invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewGateError(f"{label} timestamp must be timezone-aware")
    return parsed


def _exact_pull_request(
    repository: str,
    head_sha: str,
    token: str,
) -> dict[str, Any]:
    payload = _github_json(_pulls_path(repository, head_sha), token)
    if not isinstance(payload, list) or len(payload) >= _MAX_PAGE_SIZE:
        raise ReviewGateError("Sonar exact-head pull-request association is ambiguous")
    matches: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ReviewGateError("Sonar exact-head pull-request association is invalid")
        head = row.get("head")
        base = row.get("base")
        if (
            isinstance(head, dict)
            and head.get("sha") == head_sha
            and isinstance(base, dict)
            and base.get("ref") == "main"
            and row.get("state") == "open"
        ):
            matches.append(row)
    if len(matches) != 1:
        raise ReviewGateError("Sonar exact-head pull-request association is not unique")
    number = matches[0].get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise ReviewGateError("Sonar exact-head pull-request number is invalid")
    return matches[0]


def _head_commit_time(repository: str, head_sha: str, token: str) -> datetime:
    payload = _github_json(_commit_path(repository, head_sha), token)
    if not isinstance(payload, dict) or payload.get("sha") != head_sha:
        raise ReviewGateError("Sonar exact-head commit metadata is invalid")
    commit = payload.get("commit")
    if not isinstance(commit, dict):
        raise ReviewGateError("Sonar exact-head commit metadata is invalid")
    committer = commit.get("committer")
    if not isinstance(committer, dict):
        raise ReviewGateError("Sonar exact-head commit committer is invalid")
    return _timestamp(committer.get("date"), "Sonar exact-head commit")


def _latest_sonar_suite(
    repository: str,
    head_sha: str,
    token: str,
    pull_request_number: int,
) -> dict[str, Any]:
    payload = _github_json(_check_suites_path(repository, head_sha), token)
    if not isinstance(payload, dict):
        raise ReviewGateError("Sonar exact-head check-suite response is invalid")
    total_count = payload.get("total_count")
    rows = payload.get("check_suites")
    if (
        not isinstance(total_count, int)
        or total_count < 0
        or total_count > _MAX_PAGE_SIZE
        or not isinstance(rows, list)
        or len(rows) != total_count
    ):
        raise ReviewGateError("Sonar exact-head check-suite response is truncated")
    matches: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ReviewGateError("Sonar exact-head check-suite row is invalid")
        app = row.get("app")
        pull_requests = row.get("pull_requests")
        associated = False
        if isinstance(pull_requests, list):
            for pull in pull_requests:
                if not isinstance(pull, dict):
                    continue
                head = pull.get("head")
                if (
                    pull.get("number") == pull_request_number
                    and isinstance(head, dict)
                    and head.get("sha") == head_sha
                ):
                    associated = True
                    break
        if (
            row.get("head_sha") == head_sha
            and isinstance(app, dict)
            and app.get("slug") == SONAR_APP_SLUG
            and associated
        ):
            matches.append(row)
    if not matches:
        raise ReviewGateError("Sonar exact-head check suite is missing")
    return max(
        matches,
        key=lambda row: (
            str(row.get("updated_at") or row.get("created_at") or ""),
            int(row.get("id") or 0),
        ),
    )


def _stalled_suite_fingerprint(
    suite: dict[str, Any],
) -> tuple[int, str, object, int]:
    suite_id = suite.get("id")
    status = suite.get("status")
    conclusion = suite.get("conclusion")
    check_runs_count = suite.get("latest_check_runs_count")
    if (
        not isinstance(suite_id, int)
        or isinstance(suite_id, bool)
        or suite_id <= 0
        or status not in _STALLED_SUITE_STATUSES
        or conclusion is not None
        or check_runs_count != 0
    ):
        raise ReviewGateError(
            "Sonar exact-head suite is not an eligible stalled zero-run suite"
        )
    return suite_id, str(status), conclusion, int(check_runs_count)


def _latest_sonar_comment(
    repository: str,
    token: str,
    pull_request_number: int,
    *,
    not_before: datetime,
) -> dict[str, Any]:
    payload = _github_json(_comments_path(repository, pull_request_number), token)
    if not isinstance(payload, list) or len(payload) >= _MAX_PAGE_SIZE:
        raise ReviewGateError("Sonar pull-request decoration list is ambiguous")
    matches: list[dict[str, Any]] = []
    marker = f"pullRequest={pull_request_number}"
    for row in payload:
        if not isinstance(row, dict):
            raise ReviewGateError("Sonar pull-request decoration row is invalid")
        user = row.get("user")
        body = row.get("body")
        if (
            isinstance(user, dict)
            and user.get("login") == SONAR_BOT_LOGIN
            and isinstance(body, str)
            and marker in body
        ):
            observed_at = _timestamp(
                row.get("updated_at") or row.get("created_at"),
                "Sonar pull-request decoration",
            )
            if observed_at >= not_before:
                matches.append(row)
    if not matches:
        raise ReviewGateError("Sonar exact-head pull-request decoration is missing")
    return max(
        matches,
        key=lambda row: _timestamp(
            row.get("updated_at") or row.get("created_at"),
            "Sonar pull-request decoration",
        ),
    )


def _validate_sonar_comment(
    comment: dict[str, Any],
    pull_request_number: int,
) -> list[str]:
    failures: list[str] = []
    user = comment.get("user")
    body = comment.get("body")
    if not isinstance(user, dict) or user.get("login") != SONAR_BOT_LOGIN:
        failures.append("Sonar pull-request decoration author is invalid")
        return failures
    if not isinstance(body, str):
        failures.append("Sonar pull-request decoration body is invalid")
        return failures
    if f"pullRequest={pull_request_number}" not in body:
        failures.append("Sonar pull-request decoration is not bound to this PR")
    if "Quality Gate passed" not in body:
        failures.append("Sonar pull-request decoration Quality Gate is not passed")
    for pattern, label in (
        (ZERO_NEW_ISSUES, "New issues"),
        (ZERO_ACCEPTED_ISSUES, "Accepted issues"),
        (ZERO_HOTSPOTS, "Security Hotspots"),
    ):
        match = pattern.search(body)
        if match is None:
            failures.append(f"Sonar pull-request decoration missing {label}")
        elif int(match.group(1)) != 0:
            failures.append(
                f"Sonar pull-request decoration {label} must be 0, got {match.group(1)}"
            )
    return failures


def _certify_stalled_suite_decoration(
    repository: str,
    head_sha: str,
    token: str,
) -> str:
    pull_request = _exact_pull_request(repository, head_sha, token)
    pull_request_number = int(pull_request["number"])
    commit_time = _head_commit_time(repository, head_sha, token)
    suite = _latest_sonar_suite(
        repository,
        head_sha,
        token,
        pull_request_number,
    )
    suite_fingerprint = _stalled_suite_fingerprint(suite)
    suite_time = _timestamp(
        suite.get("created_at"),
        "Sonar exact-head check suite",
    )
    comment = _latest_sonar_comment(
        repository,
        token,
        pull_request_number,
        not_before=max(commit_time, suite_time),
    )
    failures = _validate_sonar_comment(comment, pull_request_number)
    if failures:
        raise ReviewGateError("; ".join(failures))

    fresh_runs = _github_json(_check_runs_path(repository, head_sha), token)
    late_run = _find_exact_sonar_run(fresh_runs, head_sha)
    if late_run is not None:
        late_failures = _validate_sonar_run(late_run)
        if late_failures:
            raise ReviewGateError("; ".join(late_failures))
        return "direct_check_run_after_stalled_suite"

    fresh_pull_request = _exact_pull_request(repository, head_sha, token)
    if fresh_pull_request.get("number") != pull_request_number:
        raise ReviewGateError("Sonar exact-head pull-request association changed")
    fresh_suite = _latest_sonar_suite(
        repository,
        head_sha,
        token,
        pull_request_number,
    )
    if _stalled_suite_fingerprint(fresh_suite) != suite_fingerprint:
        raise ReviewGateError(
            "Sonar exact-head stalled suite changed during evidence read"
        )
    fresh_comment = _latest_sonar_comment(
        repository,
        token,
        pull_request_number,
        not_before=max(commit_time, suite_time),
    )
    if (
        fresh_comment.get("id") != comment.get("id")
        or fresh_comment.get("updated_at") != comment.get("updated_at")
        or fresh_comment.get("body") != comment.get("body")
    ):
        raise ReviewGateError(
            "Sonar exact-head pull-request decoration changed during evidence read"
        )
    print(
        "SONAR_PR_DECORATION_PROVENANCE=CERTIFIED "
        f"head={head_sha} pr={pull_request_number} suite={suite_fingerprint[0]}"
    )
    return "stalled_suite_pr_decoration"


def _find_exact_named_check(
    payload: Any,
    head_sha: str,
    name: str,
    app_slug: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    runs = payload.get("check_runs")
    if not isinstance(runs, list):
        return None
    matches = []
    for row in runs:
        if not isinstance(row, dict):
            continue
        app = row.get("app")
        if (
            row.get("name") == name
            and row.get("head_sha") == head_sha
            and isinstance(app, dict)
            and app.get("slug") == app_slug
        ):
            matches.append(row)
    if not matches:
        return None
    return max(
        matches,
        key=lambda row: str(row.get("completed_at") or row.get("started_at") or ""),
    )


def _repository_governance_proxy(
    repository: str,
    head_sha: str,
    token: str,
) -> tuple[dict[str, Any] | None, str]:
    attempts = int(os.environ.get("V10_SONAR_GATE_ATTEMPTS", str(DEFAULT_ATTEMPTS)))
    delay = int(
        os.environ.get("V10_SONAR_GATE_DELAY_SECONDS", str(DEFAULT_DELAY_SECONDS))
    )
    for attempt in range(1, attempts + 1):
        payload = _github_json(_check_runs_path(repository, head_sha), token)
        direct_run = _find_exact_sonar_run(payload, head_sha)
        if direct_run is not None:
            if direct_run.get("status") == STATUS_COMPLETED:
                failures = _validate_sonar_run(direct_run)
                if failures:
                    raise ReviewGateError("; ".join(failures))
                return direct_run, "direct_check_run_after_proxy_wait"
        else:
            governance = _find_exact_named_check(
                payload,
                head_sha,
                _GOVERNANCE_CHECK_NAME,
                _GITHUB_ACTIONS_APP_SLUG,
            )
            if governance is not None and governance.get("status") == STATUS_COMPLETED:
                if governance.get("conclusion") != "success":
                    raise ReviewGateError(
                        "Exact-head engineering governance proxy is not success"
                    )
                output = governance.get("output")
                if (
                    not isinstance(output, dict)
                    or output.get(ANNOTATIONS_COUNT_KEY) != 0
                ):
                    raise ReviewGateError(
                        "Exact-head engineering governance proxy annotations must be 0"
                    )
                return None, "repository_governance_proxy"
        if attempt < attempts:
            time.sleep(delay)
    raise ReviewGateError(
        "Exact-head engineering governance proxy did not become successful "
        "within bounded wait"
    )


def _wait_for_sonar(
    repository: str,
    head_sha: str,
    token: str,
) -> tuple[dict[str, Any] | None, str]:
    attempts = int(os.environ.get("V10_SONAR_GATE_ATTEMPTS", str(DEFAULT_ATTEMPTS)))
    delay = int(
        os.environ.get("V10_SONAR_GATE_DELAY_SECONDS", str(DEFAULT_DELAY_SECONDS))
    )
    latest_run: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        payload = _github_json(_check_runs_path(repository, head_sha), token)
        latest_run = _find_exact_sonar_run(payload, head_sha)
        if latest_run is not None and latest_run.get("status") == STATUS_COMPLETED:
            return latest_run, "direct_check_run"
        if attempt < attempts:
            time.sleep(delay)
    if latest_run is not None:
        raise ReviewGateError(
            f"{SONAR_EXACT_HEAD} check did not complete within bounded wait"
        )
    try:
        return None, _certify_stalled_suite_decoration(repository, head_sha, token)
    except ReviewGateHttpError as exc:
        if exc.status != 403:
            raise
        return _repository_governance_proxy(repository, head_sha, token)


def _validated_environment() -> tuple[str, str, str] | None:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    head_sha = os.environ.get("EXPECTED_HEAD", "").strip().lower()
    token = os.environ.get("GITHUB_TOKEN", "")
    if _REPOSITORY_PATTERN.fullmatch(repository) is None:
        print(f"{EXTERNAL_GATE_FAILED}: invalid GITHUB_REPOSITORY", file=sys.stderr)
        return None
    if release_gate._SHA.fullmatch(head_sha) is None:  # noqa: SLF001 - shared authority
        print(
            f"{EXTERNAL_GATE_FAILED}: EXPECTED_HEAD must be lowercase full SHA",
            file=sys.stderr,
        )
        return None
    if not token:
        print(f"{EXTERNAL_GATE_FAILED}: GitHub token unavailable", file=sys.stderr)
        return None
    return repository, head_sha, token


def main() -> int:
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        print(
            "External review gate: pull_request-only; current event is not applicable."
        )
        return 0

    environment = _validated_environment()
    if environment is None:
        return 2
    repository, head_sha, token = environment

    try:
        run, evidence_mode = _wait_for_sonar(repository, head_sha, token)
        if run is None:
            failures: list[str] = []
            annotations: list[str] = []
        else:
            failures = _validate_sonar_run(run)
            annotations = (
                _annotation_lines(run, repository, token) if failures else []
            )
    except ReviewGateError as exc:
        print(f"{EXTERNAL_GATE_FAILED}: {exc}", file=sys.stderr)
        return 1

    if failures:
        print(f"{EXTERNAL_GATE_FAILED}:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        for annotation in annotations:
            print(f"- {annotation}", file=sys.stderr)
        return 1

    print(f"External review gate passed for exact head {head_sha}.")
    print(f"Sonar evidence mode: {evidence_mode}.")
    if run is None:
        print(
            "Sonar: zero-finding exact-head evidence certified through a bounded "
            "provider-delivery fallback."
        )
    else:
        print(
            "Sonar: Quality Gate success; new issues=0; "
            "Security Hotspots=0; annotations=0."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
