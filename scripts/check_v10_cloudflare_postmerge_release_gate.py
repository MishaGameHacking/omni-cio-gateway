from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, NoReturn
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


_API_BASE = "https://api.github.com"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_MAX_RESPONSE_BYTES = 1_048_576
_TRANSIENT_HTTP = frozenset({408, 429, 502, 503, 504})
_RETRY_DELAYS = (1.0, 2.0)
_DEFAULT_WAIT_SECONDS = 900
_DEFAULT_POLL_SECONDS = 15
_WORKFLOW_RUNS_PER_PAGE = 100
_CHECK_RUNS_PER_PAGE = 100
_MAX_FILTERED_WORKFLOW_RUNS = 1000
_MAX_FILTERED_CHECK_RUNS = 1000
_ZERO_NEW_ISSUES = re.compile(r"\[(\d+) New issues\]")
_ZERO_HOTSPOTS = re.compile(r"\[(\d+) Security Hotspots\]")
_CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
)
_GREEN_CHECKPOINT_CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json"
)


class ReleaseGateStopped(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        suffix = f" status={status}" if status is not None else ""
        super().__init__(f"{code}{suffix}")


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        return None


_OPENER = build_opener(_RejectRedirects())


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ReleaseGateStopped(f"{name}_REQUIRED")
    return value


def _expected_sha(value: str) -> str:
    sha = value.strip().lower()
    if _SHA.fullmatch(sha) is None:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_EXPECTED_SHA_INVALID")
    return sha


def _repository(value: str) -> str:
    repository = value.strip()
    if _REPOSITORY.fullmatch(repository) is None:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_REPOSITORY_INVALID")
    return repository


def _read_json_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID") from None
    if not isinstance(payload, dict):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID")
    return payload


def _contract() -> tuple[frozenset[str], int, str, str]:
    try:
        payload = _read_json_contract(_CONTRACT)
        gate = payload["post_merge_gate"]
        names = gate["required_core_push_workflows"]
        minimum = gate["minimum_successful_push_workflows"]

        green_payload = _read_json_contract(_GREEN_CHECKPOINT_CONTRACT)
        sonar = green_payload["sonar_review"]
        external_required = sonar["post_merge_exact_main_check_required"]
        external_name = sonar["post_merge_check_name"]
        external_app_slug = sonar["post_merge_check_app_slug"]
        external_success_only = sonar["post_merge_check_success_only"]
        missing_fallback_allowed = sonar[
            "post_merge_missing_equivalent_tree_fallback_allowed"
        ]
        missing_fallback_waited = sonar[
            "post_merge_missing_fallback_requires_bounded_wait_exhausted"
        ]
        missing_fallback_no_main_check = sonar[
            "post_merge_missing_fallback_requires_no_matching_main_check"
        ]
    except (KeyError, TypeError):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID") from None
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) or not name for name in names)
        or len(set(names)) != len(names)
    ):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID")
    if not isinstance(minimum, int) or minimum < len(names):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID")
    if (
        external_required is not True
        or external_success_only is not True
        or missing_fallback_allowed is not True
        or missing_fallback_waited is not True
        or missing_fallback_no_main_check is not True
        or not isinstance(external_name, str)
        or not external_name
        or not isinstance(external_app_slug, str)
        or not external_app_slug
    ):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID")
    return frozenset(names), minimum, external_name, external_app_slug


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "omni-cio-v10-cloudflare-postmerge-gate",
        "X-GitHub-Api-Version": "2026-03-10",
    }


def _open_api_request(path: str, headers: Mapping[str, str]) -> tuple[int, bytes]:
    request = Request(f"{_API_BASE}{path}", headers=dict(headers), method="GET")
    with _OPENER.open(request, timeout=30.0) as response:
        return int(response.status), response.read(_MAX_RESPONSE_BYTES + 1)


def _sleep_before_retry(attempt: int, attempts: int) -> bool:
    if attempt + 1 >= attempts:
        return False
    time.sleep(_RETRY_DELAYS[attempt])
    return True


def _raise_http_error(status: int) -> NoReturn:
    if status in {401, 403}:
        raise ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_GITHUB_AUTHORITY_INSUFFICIENT",
            status=status,
        )
    raise ReleaseGateStopped(
        "CLOUDFLARE_POSTMERGE_GITHUB_HTTP_ERROR",
        status=status,
    )


def _decode_api_response(status: int, raw: bytes) -> Any:
    if status != 200:
        raise ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_GITHUB_STATUS_INVALID",
            status=status,
        )
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_GITHUB_RESPONSE_TOO_LARGE")
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_GITHUB_JSON_INVALID") from None


def _api_get(path: str, token: str) -> Any:
    if not path.startswith("/repos/") or "\\" in path:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_API_PATH_INVALID")
    headers = _api_headers(token)
    attempts = len(_RETRY_DELAYS) + 1
    for attempt in range(attempts):
        try:
            status, raw = _open_api_request(path, headers)
        except HTTPError as exc:
            status = int(exc.code)
            if status in _TRANSIENT_HTTP and _sleep_before_retry(attempt, attempts):
                continue
            _raise_http_error(status)
        except OSError:
            if _sleep_before_retry(attempt, attempts):
                continue
            raise ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_GITHUB_NETWORK_ERROR"
            ) from None
        return _decode_api_response(status, raw)
    raise AssertionError("bounded GitHub API retry exhausted")


def _current_main_sha(repository: str, token: str) -> str:
    payload = _api_get(f"/repos/{repository}/commits/main", token)
    if not isinstance(payload, dict):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_MAIN_RESPONSE_INVALID")
    value = payload.get("sha")
    if not isinstance(value, str) or _SHA.fullmatch(value.lower()) is None:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_MAIN_RESPONSE_INVALID")
    return value.lower()


def _workflow_runs_query(expected_sha: str, page: int) -> str:
    return urlencode(
        {
            "branch": "main",
            "event": "push",
            "head_sha": expected_sha,
            "per_page": str(_WORKFLOW_RUNS_PER_PAGE),
            "page": str(page),
            "exclude_pull_requests": "true",
        }
    )


def _workflow_run_page(
    repository: str,
    token: str,
    expected_sha: str,
    page: int,
) -> tuple[int, list[dict[str, Any]]]:
    query = _workflow_runs_query(expected_sha, page)
    payload = _api_get(f"/repos/{repository}/actions/runs?{query}", token)
    if not isinstance(payload, dict):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUNS_RESPONSE_INVALID")
    total_count = payload.get("total_count")
    raw_rows = payload.get("workflow_runs")
    if (
        not isinstance(total_count, int)
        or total_count < 0
        or not isinstance(raw_rows, list)
    ):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUNS_RESPONSE_INVALID")
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUN_INVALID")
        rows.append(raw)
    return total_count, rows


def _workflow_runs(
    repository: str, token: str, expected_sha: str
) -> list[dict[str, Any]]:
    total_count, first_page = _workflow_run_page(repository, token, expected_sha, 1)
    if total_count > _MAX_FILTERED_WORKFLOW_RUNS:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUNS_TRUNCATED")

    page_count = max(
        1,
        (total_count + _WORKFLOW_RUNS_PER_PAGE - 1) // _WORKFLOW_RUNS_PER_PAGE,
    )
    raw_rows = list(first_page)
    for page in range(2, page_count + 1):
        observed_total, page_rows = _workflow_run_page(
            repository,
            token,
            expected_sha,
            page,
        )
        if observed_total != total_count:
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUNS_CHANGED_DURING_READ")
        raw_rows.extend(page_rows)
    if len(raw_rows) != total_count:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUNS_INCOMPLETE")

    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if (
            raw.get("head_sha") == expected_sha
            and raw.get("head_branch") == "main"
            and raw.get("event") == "push"
        ):
            rows.append(raw)
    if len(rows) != total_count:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUN_FILTER_DRIFT")
    return rows


def _check_runs_query(page: int) -> str:
    return urlencode(
        {
            "per_page": str(_CHECK_RUNS_PER_PAGE),
            "page": str(page),
            "filter": "latest",
        }
    )


def _check_run_page(
    repository: str,
    token: str,
    expected_sha: str,
    page: int,
) -> tuple[int, list[dict[str, Any]]]:
    query = _check_runs_query(page)
    payload = _api_get(
        f"/repos/{repository}/commits/{expected_sha}/check-runs?{query}",
        token,
    )
    if not isinstance(payload, dict):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECKS_RESPONSE_INVALID")
    total_count = payload.get("total_count")
    raw_rows = payload.get("check_runs")
    if (
        not isinstance(total_count, int)
        or total_count < 0
        or not isinstance(raw_rows, list)
    ):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECKS_RESPONSE_INVALID")
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECK_INVALID")
        rows.append(raw)
    return total_count, rows


def _check_runs(repository: str, token: str, expected_sha: str) -> list[dict[str, Any]]:
    total_count, first_page = _check_run_page(repository, token, expected_sha, 1)
    if total_count > _MAX_FILTERED_CHECK_RUNS:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECKS_TRUNCATED")
    page_count = max(
        1,
        (total_count + _CHECK_RUNS_PER_PAGE - 1) // _CHECK_RUNS_PER_PAGE,
    )
    rows = list(first_page)
    for page in range(2, page_count + 1):
        observed_total, page_rows = _check_run_page(
            repository,
            token,
            expected_sha,
            page,
        )
        if observed_total != total_count:
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECKS_CHANGED_DURING_READ")
        rows.extend(page_rows)
    if len(rows) != total_count:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECKS_INCOMPLETE")
    if any(row.get("head_sha") != expected_sha for row in rows):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECK_FILTER_DRIFT")
    return rows


def _latest_runs_by_name(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    ordering: dict[str, tuple[int, int]] = {}
    for row in rows:
        name = row.get("name")
        attempt = row.get("run_attempt")
        run_id = row.get("id")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(attempt, int)
            or attempt < 1
            or not isinstance(run_id, int)
            or run_id < 1
        ):
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUN_INVALID")
        candidate = (attempt, run_id)
        if name not in ordering or candidate > ordering[name]:
            ordering[name] = candidate
            latest[name] = row
    return latest


def _gate_state(
    rows: list[dict[str, Any]],
    required_names: frozenset[str],
    minimum_successful: int,
) -> tuple[bool, int]:
    latest = _latest_runs_by_name(rows)
    missing = required_names.difference(latest)
    if missing or len(latest) < minimum_successful:
        return False, len(latest)
    pending = False
    for row in latest.values():
        status = row.get("status")
        conclusion = row.get("conclusion")
        if status != "completed":
            pending = True
            continue
        if conclusion != "success":
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_PUSH_WORKFLOW_NOT_SUCCESS")
    return not pending, len(latest)


def _matching_external_checks(
    rows: list[dict[str, Any]],
    required_name: str,
    required_app_slug: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for row in rows:
        app = row.get("app")
        app_slug = app.get("slug") if isinstance(app, dict) else None
        if row.get("name") == required_name and app_slug == required_app_slug:
            matches.append(row)
    return matches


def _external_check_ordering(row: dict[str, Any]) -> tuple[str, int]:
    check_id = row.get("id")
    if not isinstance(check_id, int) or check_id < 1:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECK_INVALID")
    timestamp = row.get("completed_at") or row.get("started_at")
    if not isinstance(timestamp, str) or not timestamp:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CHECK_INVALID")
    return timestamp, check_id


def _latest_external_check(
    rows: list[dict[str, Any]],
    required_name: str,
    required_app_slug: str,
) -> dict[str, Any] | None:
    matches = _matching_external_checks(rows, required_name, required_app_slug)
    if not matches:
        return None
    return max(matches, key=_external_check_ordering)


def _external_check_output(row: dict[str, Any]) -> tuple[dict[str, Any], str]:
    output = row.get("output")
    if not isinstance(output, dict):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_OUTPUT_INVALID")
    summary = output.get("summary")
    if not isinstance(summary, str):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_SUMMARY_INVALID")
    return output, summary


def _require_zero_sonar_findings(output: dict[str, Any], summary: str) -> None:
    issue_match = _ZERO_NEW_ISSUES.search(summary)
    hotspot_match = _ZERO_HOTSPOTS.search(summary)
    if issue_match is None or hotspot_match is None:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_SUMMARY_INVALID")
    if int(issue_match.group(1)) != 0:
        raise ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NEW_ISSUES_PRESENT"
        )
    if int(hotspot_match.group(1)) != 0:
        raise ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_SECURITY_HOTSPOTS_PRESENT"
        )
    if output.get("annotations_count") != 0:
        raise ReleaseGateStopped(
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_ANNOTATIONS_PRESENT"
        )


def _external_check_state(
    rows: list[dict[str, Any]],
    required_name: str,
    required_app_slug: str,
) -> bool:
    latest = _latest_external_check(rows, required_name, required_app_slug)
    if latest is None:
        return False
    if latest.get("status") != "completed":
        return False
    if latest.get("conclusion") != "success":
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NOT_SUCCESS")
    output, summary = _external_check_output(latest)
    _require_zero_sonar_findings(output, summary)
    return True


def _validate_wait_settings(wait_seconds: int, poll_seconds: int) -> None:
    if wait_seconds < 0 or wait_seconds > 1800:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_WAIT_INVALID")
    if poll_seconds < 1 or poll_seconds > 60:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_POLL_INVALID")


def _require_current_main(repository: str, token: str, expected_sha: str) -> None:
    if _current_main_sha(repository, token) != expected_sha:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_MAIN_SUPERSEDED")


def _external_evidence_state(
    repository: str,
    token: str,
    expected_sha: str,
    external_name: str,
    external_app_slug: str,
) -> bool:
    rows = _check_runs(repository, token, expected_sha)
    latest = _latest_external_check(rows, external_name, external_app_slug)
    if latest is None or latest.get("status") != "completed":
        return False
    if latest.get("conclusion") == "success":
        output, summary = _external_check_output(latest)
        _require_zero_sonar_findings(output, summary)
        return True
    if latest.get("conclusion") != "cancelled":
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NOT_SUCCESS")

    from scripts.check_v10_sonar_equivalent_tree_provenance import (
        MERGE_SHA_CONVERGENCE_PENDING,
        certify_cancelled_exact_main_sonar,
    )

    try:
        certify_cancelled_exact_main_sonar(
            repository=repository,
            token=token,
            expected_sha=expected_sha,
            main_check=latest,
            required_name=external_name,
            required_app_slug=external_app_slug,
        )
    except RuntimeError as exc:
        code = getattr(exc, "code", None)
        status = getattr(exc, "status", None)
        if not isinstance(code, str) or not code:
            raise
        if code == MERGE_SHA_CONVERGENCE_PENDING:
            return False
        if status is not None and (
            not isinstance(status, int) or isinstance(status, bool)
        ):
            raise
        raise ReleaseGateStopped(code, status=status) from None
    return True


def _deadline_external_evidence_state(
    repository: str,
    token: str,
    expected_sha: str,
    external_name: str,
    external_app_slug: str,
) -> bool:
    rows = _check_runs(repository, token, expected_sha)
    latest = _latest_external_check(rows, external_name, external_app_slug)
    if latest is not None:
        return _external_evidence_state(
            repository,
            token,
            expected_sha,
            external_name,
            external_app_slug,
        )

    from scripts.check_v10_sonar_equivalent_tree_provenance import (
        certify_missing_exact_main_sonar,
    )

    certify_missing_exact_main_sonar(
        repository=repository,
        token=token,
        expected_sha=expected_sha,
        required_name=external_name,
        required_app_slug=external_app_slug,
    )
    return True


def _release_gate_snapshot(
    repository: str,
    token: str,
    expected_sha: str,
    required_names: frozenset[str],
    minimum_successful: int,
    external_name: str,
    external_app_slug: str,
) -> tuple[bool, int, bool]:
    _require_current_main(repository, token, expected_sha)
    ready, observed = _gate_state(
        _workflow_runs(repository, token, expected_sha),
        required_names,
        minimum_successful,
    )
    external_ready = _external_evidence_state(
        repository,
        token,
        expected_sha,
        external_name,
        external_app_slug,
    )
    return ready, observed, external_ready


def _pending_gate_code(workflows_ready: bool) -> str:
    if not workflows_ready:
        return "CLOUDFLARE_POSTMERGE_PUSH_WORKFLOWS_PENDING"
    return "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_PENDING"


def wait_for_release_gate(
    expected_sha: str,
    *,
    environ: Mapping[str, str] | None = None,
    wait_seconds: int = _DEFAULT_WAIT_SECONDS,
    poll_seconds: int = _DEFAULT_POLL_SECONDS,
) -> int:
    _validate_wait_settings(wait_seconds, poll_seconds)
    environment = os.environ if environ is None else environ
    sha = _expected_sha(expected_sha)
    repository = _repository(_required(environment, "GITHUB_REPOSITORY"))
    token = _required(environment, "GITHUB_TOKEN")
    required_names, minimum_successful, external_name, external_app_slug = _contract()
    deadline = time.monotonic() + float(wait_seconds)
    while True:
        ready, observed, external_ready = _release_gate_snapshot(
            repository,
            token,
            sha,
            required_names,
            minimum_successful,
            external_name,
            external_app_slug,
        )
        if ready and external_ready:
            _require_current_main(repository, token, sha)
            print(
                "CLOUDFLARE_POSTMERGE_GATE=READY "
                f"exact_sha={sha} push_workflows={observed} "
                f"external_check={external_name}"
            )
            return observed
        if time.monotonic() >= deadline:
            if ready and _deadline_external_evidence_state(
                repository,
                token,
                sha,
                external_name,
                external_app_slug,
            ):
                _require_current_main(repository, token, sha)
                print(
                    "CLOUDFLARE_POSTMERGE_GATE=READY "
                    f"exact_sha={sha} push_workflows={observed} "
                    f"external_check={external_name} "
                    "evidence=bounded_equivalent_tree"
                )
                return observed
            raise ReleaseGateStopped(_pending_gate_code(ready))
        time.sleep(min(float(poll_seconds), max(0.0, deadline - time.monotonic())))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--wait-seconds", type=int, default=_DEFAULT_WAIT_SECONDS)
    parser.add_argument("--poll-seconds", type=int, default=_DEFAULT_POLL_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        wait_for_release_gate(
            args.expected_sha,
            wait_seconds=args.wait_seconds,
            poll_seconds=args.poll_seconds,
        )
    except ReleaseGateStopped as exc:
        fields = ["CLOUDFLARE_POSTMERGE_GATE=STOPPED", f"code={exc.code}"]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
