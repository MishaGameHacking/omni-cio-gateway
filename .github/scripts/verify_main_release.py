"""Require successful, current main checks before Timeweb administration."""

from __future__ import annotations

import http.client
import json
import os
import re
import sys
import time
from contextlib import closing
from typing import Any
from urllib.parse import parse_qs, urlsplit

REPOSITORY = "MishaGameHacking/omni-cio-gateway"
FOUNDATION_PATH = ".github/workflows/auth-foundation-ci.yml"
SONAR_PROJECT = "MishaGameHacking_omni-cio-gateway"
MAX_RESPONSE_BYTES = 2_000_000


class ReleaseBlocked(RuntimeError):
    """No production mutation is allowed with the available evidence."""


class PendingChecks(RuntimeError):
    """The exact main checks have not completed yet."""


class GitHubClient:
    def __init__(self, token: str, *, deadline: float) -> None:
        self.token = token
        self.deadline = deadline

    def get(self, path: str) -> dict[str, Any]:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ReleaseBlocked("Timed out waiting for accepted main checks")
        try:
            with closing(http.client.HTTPSConnection(
                "api.github.com", timeout=min(15, remaining),
            )) as connection:
                connection.request("GET", f"/repos/{REPOSITORY}{path}", headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "omnicio-release-gate/1.0",
                })
                response = connection.getresponse()
                # Do not follow redirects or forward credentials to another host.
                if response.status != 200:
                    raise ReleaseBlocked("GitHub did not return verification data")
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ReleaseBlocked("GitHub verification response is too large")
                data = json.loads(body)
        except (OSError, http.client.HTTPException, ValueError):
            raise ReleaseBlocked("GitHub verification is unavailable or malformed") from None
        if not isinstance(data, dict):
            raise ReleaseBlocked("GitHub verification response is not an object")
        return data

    def collect(self, path: str, key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, 11):
            data = self.get(f"{path}&per_page=100&page={page}")
            batch = data.get(key)
            if not isinstance(batch, list) or not all(isinstance(item, dict) for item in batch):
                raise ReleaseBlocked("GitHub verification list is malformed")
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise ReleaseBlocked("GitHub verification pagination limit exceeded")


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
        if len(numbers) == 1 and re.fullmatch(r"[1-9][0-9]*", numbers[0]):
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


def require_sonar(checks: list[dict[str, Any]], sha: str) -> None:
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


def require_foundation(runs: list[dict[str, Any]], sha: str) -> None:
    candidates = [
        run for run in runs
        if run.get("head_sha") == sha
        and run.get("head_branch") == "main"
        and run.get("event") == "push"
        and run.get("path") == FOUNDATION_PATH
        and isinstance(run.get("repository"), dict)
        and run["repository"].get("full_name") == REPOSITORY
    ]
    require_success(latest(candidates, "main foundation CI"), "Main foundation CI")


def require_current_main(client: GitHubClient, sha: str) -> None:
    commit = client.get("/branches/main").get("commit")
    if not isinstance(commit, dict) or commit.get("sha") != sha:
        raise ReleaseBlocked("Release SHA is no longer the current main")


def verify(client: GitHubClient, sha: str) -> None:
    require_current_main(client, sha)
    # filter=all is essential: a later PR analysis can hide main's failed check.
    checks = client.collect(f"/commits/{sha}/check-runs?filter=all", "check_runs")
    require_sonar(checks, sha)
    runs = client.collect(
        f"/actions/workflows/auth-foundation-ci.yml/runs?event=push&head_sha={sha}",
        "workflow_runs",
    )
    require_foundation(runs, sha)
    require_current_main(client, sha)


def wait_for_release(client: GitHubClient, sha: str) -> None:
    while True:
        try:
            verify(client, sha)
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


def main() -> int:
    try:
        sha, token = release_context()
        client = GitHubClient(token, deadline=time.monotonic() + 600)
        wait_for_release(client, sha)
    except ReleaseBlocked as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(f"Accepted main verified: {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
