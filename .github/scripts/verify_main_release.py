"""Require successful, current main checks before Timeweb administration."""

from __future__ import annotations

import http.client
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

REPOSITORY = "MishaGameHacking/omni-cio-gateway"
FOUNDATION_PATH = ".github/workflows/auth-foundation-ci.yml"
APPLICATION_PATH = ".github/workflows/auth-app-deploy.yml"
APPLICATION_TEST_JOB = "Test auth deployer"
SONAR_PROJECT = "MishaGameHacking_omni-cio-gateway"
SONAR_ANALYSES_PATH = (
    f"/api/project_analyses/search?project={SONAR_PROJECT}&branch=main&p=1&ps=1"
)
SONAR_ISSUES_PATH = (
    f"/api/issues/search?componentKeys={SONAR_PROJECT}&branch=main"
    "&issueStatuses=OPEN,CONFIRMED,ACCEPTED&p=1&ps=1"
)
MAX_RESPONSE_BYTES = 2_000_000


class ReleaseBlocked(RuntimeError):
    """No production mutation is allowed with the available evidence."""


class PendingChecks(RuntimeError):
    """The exact main checks have not completed yet."""


def request_json(
    host: str, path: str, headers: dict[str, str], *, deadline: float, label: str,
) -> Any:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ReleaseBlocked("Timed out waiting for accepted main checks")
    try:
        with closing(http.client.HTTPSConnection(
            host, timeout=min(15, remaining),
        )) as connection:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            # Redirects are never followed, so credentials stay on their fixed host.
            if response.status in {408, 429} or 500 <= response.status <= 599:
                raise PendingChecks(f"{label} verification is temporarily unavailable")
            if response.status != 200:
                raise ReleaseBlocked(
                    f"{label} did not return verification data (HTTP {response.status})"
                )
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ReleaseBlocked(f"{label} verification response is too large")
            if time.monotonic() >= deadline:
                raise ReleaseBlocked("Timed out waiting for accepted main checks")
            try:
                return json.loads(body)
            except ValueError:
                raise ReleaseBlocked(f"{label} verification response is malformed") from None
    except PendingChecks:
        raise
    except (OSError, http.client.HTTPException):
        raise PendingChecks(f"{label} verification is temporarily unavailable") from None


class GitHubClient:
    def __init__(self, token: str, *, deadline: float) -> None:
        self.token = token
        self.deadline = deadline

    def _request(self, path: str) -> Any:
        return request_json("api.github.com", f"/repos/{REPOSITORY}{path}", {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "omnicio-release-gate/1.0",
        }, deadline=self.deadline, label="GitHub")

    def get(self, path: str) -> dict[str, Any]:
        data = self._request(path)
        if not isinstance(data, dict):
            raise ReleaseBlocked("GitHub verification response is not an object")
        return data

    def get_list(self, path: str) -> list[dict[str, Any]]:
        data = self._request(path)
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ReleaseBlocked("GitHub verification response is not an object list")
        return data

    def collect(self, path: str, key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 11):
            data = self.get(f"{path}{separator}per_page=100&page={page}")
            batch = data.get(key)
            if not isinstance(batch, list) or not all(isinstance(item, dict) for item in batch):
                raise ReleaseBlocked("GitHub verification list is malformed")
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise ReleaseBlocked("GitHub verification pagination limit exceeded")


class SonarClient:
    """Read overall evidence on the fixed EU project; never reuse GitHub auth."""

    def __init__(self, token: str, *, deadline: float) -> None:
        if token and re.fullmatch(r"[\x21-\x7e]{1,512}", token) is None:
            raise ReleaseBlocked("SonarCloud verification token is malformed")
        self.token = token
        self.deadline = deadline

    def get(self, path: str) -> dict[str, Any]:
        if path not in {SONAR_ANALYSES_PATH, SONAR_ISSUES_PATH}:
            raise ReleaseBlocked("SonarCloud verification scope is invalid")
        headers = {
            "Accept": "application/json", "Cache-Control": "no-cache",
            "User-Agent": "omnicio-release-gate/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = request_json(
            "sonarcloud.io", path, headers, deadline=self.deadline, label="SonarCloud",
        )
        if not isinstance(data, dict):
            raise ReleaseBlocked("SonarCloud verification response is not an object")
        return data


def sonar_first_page(data: dict[str, Any], key: str) -> tuple[int, list[dict[str, Any]]]:
    """Validate the API's total, not the size of a possibly truncated page."""
    paging = data.get("paging")
    if not isinstance(paging, dict):
        raise ReleaseBlocked("SonarCloud inventory paging is missing")
    for field in ("pageIndex", "pageSize", "total"):
        if type(paging.get(field)) is not int:
            raise ReleaseBlocked("SonarCloud inventory paging is malformed")
    if paging["pageIndex"] != 1 or paging["pageSize"] != 1 or paging["total"] < 0:
        raise ReleaseBlocked("SonarCloud inventory page does not match its request")
    # V1 may include these deprecated aliases; contradictory counts cannot pass.
    for old, current in (("p", "pageIndex"), ("ps", "pageSize"), ("total", "total")):
        if old in data and (type(data[old]) is not int or data[old] != paging[current]):
            raise ReleaseBlocked("SonarCloud inventory totals are inconsistent")
    rows = data.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ReleaseBlocked("SonarCloud inventory list is malformed")
    if len(rows) != min(paging["total"], 1):
        raise ReleaseBlocked("SonarCloud inventory list is incomplete")
    return paging["total"], rows


def current_sonar_analysis(client: SonarClient, sha: str) -> tuple[str, str, str]:
    """The API sorts processed analyses newest first; a PR result is not queried."""
    _, analyses = sonar_first_page(client.get(SONAR_ANALYSES_PATH), "analyses")
    if not analyses:
        raise PendingChecks("Waiting for SonarCloud overall main analysis")
    analysis = analyses[0]
    key, revision, date = (analysis.get(field) for field in ("key", "revision", "date"))
    if not isinstance(key, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", key) is None:
        raise ReleaseBlocked("SonarCloud analysis identity is malformed")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ReleaseBlocked("SonarCloud analysis is missing a valid source revision")
    if not isinstance(date, str):
        raise ReleaseBlocked("SonarCloud analysis date is missing")
    try:
        timestamp = datetime.fromisoformat(date)
    except ValueError:
        raise ReleaseBlocked("SonarCloud analysis date is malformed") from None
    if timestamp.tzinfo is None:
        raise ReleaseBlocked("SonarCloud analysis date has no time zone")
    if revision != sha:
        raise PendingChecks("Waiting for SonarCloud overall analysis of the exact main SHA")
    return key, revision, date


def require_overall_sonar(client: SonarClient, sha: str) -> None:
    before = current_sonar_analysis(client, sha)
    # No new-code/date/assignee/rule filter: even one older or accepted issue blocks.
    total, _ = sonar_first_page(client.get(SONAR_ISSUES_PATH), "issues")
    if total != 0:
        raise ReleaseBlocked("SonarCloud overall main has Open, Confirmed or Accepted issues")
    if current_sonar_analysis(client, sha) != before:
        raise PendingChecks("SonarCloud main analysis changed during inventory verification")


def sonar_scope(check: dict[str, Any]) -> str:
    """A PR result can share main's SHA and must never certify main."""
    url = check.get("details_url")
    if not isinstance(url, str):
        return "unknown"
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
    except ValueError:
        return "unknown"
    if (parsed.scheme, parsed.netloc, parsed.path) != (
        "https", "sonarcloud.io", "/dashboard",
    ) or parsed.fragment or query.get("id") != [SONAR_PROJECT]:
        return "unknown"
    if set(query) == {"id", "branch"} and query["branch"] == ["main"]:
        return "main"
    if set(query) == {"id", "pullRequest"}:
        numbers = query["pullRequest"]
        if len(numbers) == 1 and re.fullmatch(r"[1-9]\d*", numbers[0], flags=re.ASCII):
            return "pr"
    return "unknown"


def latest(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not rows:
        raise PendingChecks(f"Waiting for {label}")
    if any(type(row.get("id")) is not int or row["id"] <= 0 for row in rows):
        raise ReleaseBlocked("GitHub verification identity is malformed")
    return max(rows, key=lambda row: row["id"])


def require_success(row: dict[str, Any], label: str) -> None:
    if row.get("status") != "completed":
        raise PendingChecks(f"Waiting for {label}")
    if row.get("conclusion") != "success":
        raise ReleaseBlocked(f"{label} did not pass; production must remain unchanged")


def sonar_summary_count(summary: str, label: str) -> int:
    match = re.search(rf"\[(\d+) {re.escape(label)}s?\]", summary)
    if match is None:
        raise ReleaseBlocked(f"SonarCloud summary is missing {label} count")
    return int(match.group(1))


def require_clean_sonar_output(check: dict[str, Any]) -> None:
    output = check.get("output")
    if not isinstance(output, dict):
        raise ReleaseBlocked("SonarCloud result is missing output")
    annotations = output.get("annotations_count")
    if type(annotations) is not int or annotations < 0:
        raise ReleaseBlocked("SonarCloud annotation count is malformed")
    if annotations != 0:
        raise ReleaseBlocked("SonarCloud has unresolved annotations")

    summary = output.get("summary")
    if not isinstance(summary, str) or not summary:
        raise ReleaseBlocked("SonarCloud result is missing issue summary")
    counts = {
        "New issue": sonar_summary_count(summary, "New issue"),
        "Accepted issue": sonar_summary_count(summary, "Accepted issue"),
        "Security Hotspot": sonar_summary_count(summary, "Security Hotspot"),
    }
    nonzero = [label for label, count in counts.items() if count != 0]
    if nonzero:
        raise ReleaseBlocked(
            "SonarCloud is not zero-issue clean: " + ", ".join(nonzero)
        )


def require_sonar(checks: list[dict[str, Any]], sha: str) -> tuple[int, str]:
    candidates = [
        check for check in checks
        if check.get("head_sha") == sha
        and check.get("name") == "SonarCloud Code Analysis"
        and isinstance(check.get("app"), dict)
        and check["app"].get("id") == 12526
        and check["app"].get("slug") == "sonarqubecloud"
        and sonar_scope(check) != "pr"
    ]
    check = latest(candidates, "main SonarCloud analysis")
    if sonar_scope(check) != "main":
        raise PendingChecks("Waiting for unambiguous main SonarCloud analysis")
    require_success(check, "Main SonarCloud analysis")
    require_clean_sonar_output(check)
    completed_at = check.get("completed_at")
    if not isinstance(completed_at, str) or not completed_at:
        raise ReleaseBlocked("SonarCloud check completion identity is missing")
    return check["id"], completed_at


def latest_push_run(
    runs: list[dict[str, Any]], sha: str, path: str, label: str,
) -> dict[str, Any]:
    candidates = [
        run for run in runs
        if run.get("head_sha") == sha
        and run.get("head_branch") == "main"
        and run.get("event") == "push"
        and run.get("path") == path
        and isinstance(run.get("repository"), dict)
        and run["repository"].get("full_name") == REPOSITORY
    ]
    latest(candidates, label)  # Validate every candidate's run identity before ordering.
    if any(type(run.get("run_attempt")) is not int or run["run_attempt"] < 1
           for run in candidates):
        raise ReleaseBlocked("GitHub workflow attempt identity is malformed")
    return max(candidates, key=lambda run: (run["id"], run["run_attempt"]))


def require_foundation(runs: list[dict[str, Any]], sha: str) -> None:
    run = latest_push_run(runs, sha, FOUNDATION_PATH, "main foundation CI")
    require_success(run, "Main foundation CI")


def require_application_tests(client: GitHubClient, sha: str) -> None:
    """A downstream deployment can never replace the exact push's tests.

    Only the tests job is required: waiting for the whole deployment workflow
    would couple this gate to its own deploy job. The attempt-scoped endpoint
    prevents a previous green attempt from hiding a rerun's failure or pending job.
    """
    path = f"/actions/workflows/auth-app-deploy.yml/runs?event=push&head_sha={sha}"
    label = "main auth application push tests"
    run = latest_push_run(client.collect(path, "workflow_runs"), sha, APPLICATION_PATH, label)
    jobs = client.collect(
        f"/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs",
    )
    candidates = [
        job for job in jobs
        if job.get("name") == APPLICATION_TEST_JOB
        and job.get("run_id") == run["id"]
        and job.get("head_sha") == sha
        and job.get("head_branch") == "main"
    ]
    if len(candidates) > 1:
        raise ReleaseBlocked("Main auth application test job is ambiguous")
    if not candidates and run.get("status") == "completed":
        raise ReleaseBlocked("Main auth application push is missing its tests job")
    job = latest(candidates, label)
    # This field is optional in the documented job DTO; the endpoint itself
    # selects the attempt. If supplied, contradictory attribution is rejected.
    if "run_attempt" in job and (
        type(job["run_attempt"]) is not int or job["run_attempt"] != run["run_attempt"]
    ):
        raise ReleaseBlocked("Main auth application test attempt does not match")
    require_success(job, "Main auth application push tests")
    current = latest_push_run(
        client.collect(path, "workflow_runs"), sha, APPLICATION_PATH, label,
    )
    if (current["id"], current["run_attempt"]) != (run["id"], run["run_attempt"]):
        raise PendingChecks("Main auth application push attempt changed during verification")


def require_current_main(client: GitHubClient, sha: str) -> None:
    commit = client.get("/branches/main").get("commit")
    if not isinstance(commit, dict) or commit.get("sha") != sha:
        raise ReleaseBlocked("Release SHA is no longer the current main")


def verify(client: GitHubClient, sha: str, sonar: SonarClient) -> None:
    require_current_main(client, sha)
    # filter=all is essential: a later PR analysis can hide main's failed check.
    checks = client.collect(f"/commits/{sha}/check-runs?filter=all", "check_runs")
    sonar_check = require_sonar(checks, sha)
    runs = client.collect(
        f"/actions/workflows/auth-foundation-ci.yml/runs?event=push&head_sha={sha}",
        "workflow_runs",
    )
    require_foundation(runs, sha)
    require_application_tests(client, sha)
    require_overall_sonar(sonar, sha)
    current_checks = client.collect(f"/commits/{sha}/check-runs?filter=all", "check_runs")
    if require_sonar(current_checks, sha) != sonar_check:
        raise PendingChecks("SonarCloud main check changed during inventory verification")
    require_current_main(client, sha)


def wait_for_release(client: GitHubClient, sha: str, sonar: SonarClient) -> None:
    while True:
        try:
            verify(client, sha, sonar)
            return
        except PendingChecks as exc:
            remaining = client.deadline - time.monotonic()
            if remaining <= 0:
                raise ReleaseBlocked("Timed out waiting for accepted main checks") from None
            print(str(exc), flush=True)
            time.sleep(min(15, remaining))


def release_context() -> tuple[str, str]:
    sha = os.environ.get("GITHUB_SHA", "")
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") not in {
                "push", "schedule", "workflow_run", "workflow_dispatch",
            }
            or re.fullmatch(r"[0-9a-f]{40}", sha) is None):
        raise ReleaseBlocked("Only an exact main production event can pass the release gate")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ReleaseBlocked("GitHub verification token is missing")
    return sha, token


def git_executable() -> str:
    """Return a trusted OS Git binary without relying on a mutable PATH."""
    if os.name == "nt":
        program_files = pathlib.Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files"))
        candidates = (
            program_files / "Git" / "cmd" / "git.exe",
            program_files / "Git" / "bin" / "git.exe",
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        raise ReleaseBlocked("Trusted Git for Windows executable is unavailable")
    if os.name == "posix":
        return "/usr/bin/git"
    raise ReleaseBlocked(f"Unsupported release controller operating system: {os.name}")


def require_checkout(sha: str) -> None:
    """The trusted main checkout must contain exactly the requested release."""
    try:
        result = subprocess.run(
            [git_executable(), "rev-parse", "--verify", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        raise ReleaseBlocked("Unable to verify the production checkout") from None
    if result.stdout.strip() != sha:
        raise ReleaseBlocked("Production checkout differs from the release SHA")


def main() -> int:
    try:
        sha, token = release_context()
        require_checkout(sha)
        # Cover the 12-minute application check plus runner startup and cleanup.
        client = GitHubClient(token, deadline=time.monotonic() + 900)
        sonar_token = os.environ.get("SONAR_TOKEN", "")
        if sonar_token and sonar_token == token:
            raise ReleaseBlocked("SonarCloud verification must not reuse the GitHub token")
        sonar = SonarClient(sonar_token, deadline=client.deadline)
        wait_for_release(client, sha, sonar)
    except ReleaseBlocked as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(f"Accepted main verified: {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
