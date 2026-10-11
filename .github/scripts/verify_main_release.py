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
from typing import Any
from urllib.parse import parse_qs, urlsplit

REPOSITORY = "MishaGameHacking/omni-cio-gateway"
FOUNDATION_PATH = ".github/workflows/auth-foundation-ci.yml"
APPLICATION_PATH = ".github/workflows/auth-app-deploy.yml"
APPLICATION_TEST_JOB = "Test auth deployer"
POSTGRES_PATH = ".github/workflows/auth-postgres.yml"
POSTGRES_TEST_JOB = "Test PostgreSQL reconciler"
SONAR_PROJECT = "MishaGameHacking_omni-cio-gateway"
MAX_RESPONSE_BYTES = 2_000_000
RELEASE_TIMEOUT = "Timed out waiting for accepted main checks"
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")


class ReleaseBlocked(RuntimeError):
    """No production mutation is allowed with the available evidence."""


class PendingChecks(RuntimeError):
    """The exact main checks have not completed yet."""


def request_json(
    host: str, path: str, headers: dict[str, str], *, deadline: float, label: str,
) -> Any:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ReleaseBlocked(RELEASE_TIMEOUT)
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
                raise ReleaseBlocked(RELEASE_TIMEOUT)
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

    def collect_list(self, path: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, 11):
            batch = self.get_list(f"{path}?per_page=100&page={page}")
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise ReleaseBlocked("GitHub pull request pagination limit exceeded")


def sonar_scope(check: dict[str, Any]) -> str:
    """Attribute trusted results to the exact project and PR, never just its SHA."""
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
            return f"pr:{numbers[0]}"
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
    matches = re.findall(rf"\[(\d+) {re.escape(label)}s?\]", summary)
    if len(matches) != 1:
        raise ReleaseBlocked(f"SonarCloud summary has no unambiguous {label} count")
    return int(matches[0])


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


def require_sonar(
    checks: list[dict[str, Any]], sha: str, pull_number: int,
) -> tuple[int, str]:
    candidates = [
        check for check in checks
        if check.get("head_sha") == sha
        and check.get("name") == "SonarCloud Code Analysis"
        and isinstance(check.get("app"), dict)
        and check["app"].get("id") == 12526
        and check["app"].get("slug") == "sonarqubecloud"
        and sonar_scope(check) in {"unknown", f"pr:{pull_number}"}
    ]
    check = latest(candidates, "merged PR SonarCloud analysis")
    if sonar_scope(check) != f"pr:{pull_number}":
        raise PendingChecks("Waiting for unambiguous merged PR SonarCloud analysis")
    require_success(check, "Merged PR SonarCloud analysis")
    require_clean_sonar_output(check)
    completed_at = check.get("completed_at")
    if not isinstance(completed_at, str) or not completed_at:
        raise ReleaseBlocked("SonarCloud check completion identity is missing")
    return check["id"], completed_at


def merged_pull_request(client: GitHubClient, sha: str, number: int) -> tuple[int, str, str]:
    """Read the merged PR itself; an association or an open PR is not acceptance."""
    pull = client.get(f"/pulls/{number}")
    if (type(pull.get("number")) is not int or pull["number"] != number
            or pull.get("merged") is not True or pull.get("state") != "closed"
            or pull.get("merge_commit_sha") != sha):
        raise ReleaseBlocked("Release SHA is not the accepted merge of this pull request")
    for key in ("base", "head"):
        ref = pull.get(key)
        if (not isinstance(ref, dict) or not isinstance(ref.get("repo"), dict)
                or ref["repo"].get("full_name") != REPOSITORY):
            raise ReleaseBlocked("Merged pull request source repository is not trusted")
    if pull["base"].get("ref") != "main":
        raise ReleaseBlocked("Merged pull request did not target main")
    head = pull["head"].get("sha")
    merged_at = pull.get("merged_at")
    if (not isinstance(head, str) or GIT_SHA_RE.fullmatch(head) is None
            or not isinstance(merged_at, str) or not merged_at):
        raise ReleaseBlocked("Merged pull request source identity is missing")
    return number, head, merged_at


def commit_tree(client: GitHubClient, sha: str) -> str:
    commit = client.get(f"/git/commits/{sha}")
    tree = commit.get("tree")
    if commit.get("sha") != sha or not isinstance(tree, dict):
        raise ReleaseBlocked("GitHub commit tree identity is malformed")
    tree_sha = tree.get("sha")
    if not isinstance(tree_sha, str) or GIT_SHA_RE.fullmatch(tree_sha) is None:
        raise ReleaseBlocked("GitHub commit tree SHA is malformed")
    return tree_sha


def accepted_pull_request(client: GitHubClient, sha: str) -> tuple[int, str, str]:
    rows = client.collect_list(f"/commits/{sha}/pulls")
    candidates = [pull for pull in rows if pull.get("merge_commit_sha") == sha]
    if not candidates:
        raise PendingChecks("Waiting for merged pull request provenance for accepted main")
    if len(candidates) != 1:
        raise ReleaseBlocked("Accepted main pull request provenance is ambiguous")
    number = candidates[0].get("number")
    if type(number) is not int or number <= 0:
        raise ReleaseBlocked("Merged pull request number is malformed")
    identity = merged_pull_request(client, sha, number)
    # Squash changes commit identity, but may not introduce unanalysed source.
    if commit_tree(client, sha) != commit_tree(client, identity[1]):
        raise ReleaseBlocked("Accepted main tree differs from the Sonar-checked PR head tree")
    return identity


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


def require_foundation(runs: list[dict[str, Any]], sha: str) -> tuple[int, int]:
    run = latest_push_run(runs, sha, FOUNDATION_PATH, "main foundation CI")
    require_success(run, "Main foundation CI")
    return run["id"], run["run_attempt"]


def require_push_tests(
    client: GitHubClient, sha: str, workflow: str, job_name: str, label: str,
) -> tuple[int, int, int]:
    """A downstream deployment can never replace the exact push's tests.

    Only the tests job is required: waiting for the whole deployment workflow
    would couple this gate to its own deploy job. The attempt-scoped endpoint
    prevents a previous green attempt from hiding a rerun's failure or pending job.
    """
    filename = workflow.rsplit("/", 1)[-1]
    path = f"/actions/workflows/{filename}/runs?event=push&head_sha={sha}"
    run = latest_push_run(client.collect(path, "workflow_runs"), sha, workflow, label)
    jobs = client.collect(
        f"/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs",
    )
    candidates = [
        job for job in jobs
        if job.get("name") == job_name
        and job.get("run_id") == run["id"]
        and job.get("head_sha") == sha
        and job.get("head_branch") == "main"
    ]
    if len(candidates) > 1:
        raise ReleaseBlocked(f"{label} job is ambiguous")
    if not candidates and run.get("status") == "completed":
        raise ReleaseBlocked(f"{label} is missing its tests job")
    job = latest(candidates, label)
    # This field is optional in the documented job DTO; the endpoint itself
    # selects the attempt. If supplied, contradictory attribution is rejected.
    if "run_attempt" in job and (
        type(job["run_attempt"]) is not int or job["run_attempt"] != run["run_attempt"]
    ):
        raise ReleaseBlocked(f"{label} attempt does not match")
    require_success(job, label)
    current = latest_push_run(
        client.collect(path, "workflow_runs"), sha, workflow, label,
    )
    if (current["id"], current["run_attempt"]) != (run["id"], run["run_attempt"]):
        raise PendingChecks(f"{label} attempt changed during verification")
    return run["id"], run["run_attempt"], job["id"]


def require_application_tests(client: GitHubClient, sha: str) -> tuple[int, int, int]:
    return require_push_tests(
        client, sha, APPLICATION_PATH, APPLICATION_TEST_JOB, "Main auth application push tests",
    )


def require_main_ci(client: GitHubClient, sha: str) -> tuple[tuple[int, ...], ...]:
    runs = client.collect(
        f"/actions/workflows/auth-foundation-ci.yml/runs?event=push&head_sha={sha}",
        "workflow_runs",
    )
    return (
        require_foundation(runs, sha),
        require_application_tests(client, sha),
        require_push_tests(
            client, sha, POSTGRES_PATH, POSTGRES_TEST_JOB, "Main PostgreSQL push tests",
        ),
    )


def require_current_main(client: GitHubClient, sha: str) -> None:
    commit = client.get("/branches/main").get("commit")
    if not isinstance(commit, dict) or commit.get("sha") != sha:
        raise ReleaseBlocked("Release SHA is no longer the current main")


def verify_accepted_release(client: GitHubClient, sha: str) -> None:
    """Verify a previously accepted main release, including its exact tree and CI."""
    pull = accepted_pull_request(client, sha)
    number, head, _ = pull
    # The owner's release policy requires PR Sonar, not main LOC/overall analysis.
    path = f"/commits/{head}/check-runs?filter=all"
    sonar_check = require_sonar(client.collect(path, "check_runs"), head, number)
    ci = require_main_ci(client, sha)
    if require_main_ci(client, sha) != ci:
        raise PendingChecks("Main CI attempt changed during verification")
    if merged_pull_request(client, sha, number) != pull:
        raise PendingChecks("Merged PR head changed during verification")
    if require_sonar(client.collect(path, "check_runs"), head, number) != sonar_check:
        raise PendingChecks("Merged PR SonarCloud check changed during verification")


def verify(client: GitHubClient, sha: str) -> None:
    require_current_main(client, sha)
    verify_accepted_release(client, sha)
    require_current_main(client, sha)


def wait_for_release(client: GitHubClient, sha: str) -> None:
    while True:
        try:
            verify(client, sha)
            return
        except PendingChecks as exc:
            remaining = client.deadline - time.monotonic()
            if remaining <= 0:
                raise ReleaseBlocked(RELEASE_TIMEOUT) from None
            print(str(exc), flush=True)
            time.sleep(min(15, remaining))


def wait_for_main_release(sha: str, github_token: str, *, timeout: int = 900) -> None:
    """All production callers use accepted-main CI and its merged PR's Sonar proof."""
    deadline = time.monotonic() + timeout
    client = GitHubClient(github_token, deadline=deadline)
    wait_for_release(client, sha)


def release_context() -> tuple[str, str]:
    sha = os.environ.get("GITHUB_SHA", "")
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") not in {
                "push", "schedule", "workflow_run", "workflow_dispatch",
            }
            or GIT_SHA_RE.fullmatch(sha) is None):
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
        wait_for_main_release(sha, token)
    except ReleaseBlocked as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(f"Accepted main verified: {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
