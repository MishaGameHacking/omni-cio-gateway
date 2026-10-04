"""Print exact-source Sonar findings using read-only GitHub check access."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from verify_main_release import GitHubClient, PendingChecks, ReleaseBlocked


def report_annotations(client: GitHubClient, check: dict[str, Any]) -> None:
    print(check.get("output", {}).get("summary", "No summary"))
    for page in range(1, 11):
        items = client.get_list(
            f"/check-runs/{int(check['id'])}/annotations?per_page=100&page={page}"
        )
        for item in items:
            print(json.dumps({key: item.get(key) for key in (
                "path", "start_line", "end_line", "title", "message",
            )}, ensure_ascii=True))
        if len(items) < 100:
            return
    raise ReleaseBlocked("Too many Sonar annotations")


def completed_sonar(client: GitHubClient, sha: str) -> dict[str, Any] | None:
    checks = client.collect(f"/commits/{sha}/check-runs?filter=latest", "check_runs")
    sonar = [row for row in checks if row.get("name") == "SonarCloud Code Analysis"]
    if not sonar:
        return None
    check = max(sonar, key=lambda row: row["id"])
    return check if check.get("status") == "completed" else None


def main() -> None:
    sha = os.environ["SOURCE_SHA"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha, flags=re.ASCII):
        raise ReleaseBlocked("Invalid source SHA")
    deadline = time.monotonic() + 240
    client = GitHubClient(os.environ["GH_TOKEN"], deadline=deadline)
    while time.monotonic() < deadline:
        try:
            check = completed_sonar(client, sha)
        except PendingChecks:
            time.sleep(10)
            continue
        if check is not None:
            report_annotations(client, check)
            return
        time.sleep(10)
    raise ReleaseBlocked("Sonar diagnostics did not become available before the deadline")


if __name__ == "__main__":
    main()
