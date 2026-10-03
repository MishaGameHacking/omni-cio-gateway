#!/usr/bin/env python3
"""Read open GitHub code-scanning alerts without mutating repository state."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def main() -> int:
    repo = os.environ["GH_REPO"]
    token = os.environ["GH_TOKEN"]
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/code-scanning/alerts?state=open&per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "omni-cio-security-diagnostics/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            alerts = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub code-scanning API returned HTTP {exc.code}: {body[:500]}"
        ) from exc

    safe = []
    for alert in alerts:
        instance = alert.get("most_recent_instance") or {}
        tool = alert.get("tool") or {}
        rule = alert.get("rule") or {}
        safe.append(
            {
                "number": alert.get("number"),
                "state": alert.get("state"),
                "rule_id": rule.get("id"),
                "rule_severity": rule.get("severity"),
                "rule_security_severity_level": rule.get("security_severity_level"),
                "rule_description": rule.get("description"),
                "tool": tool.get("name"),
                "ref": instance.get("ref"),
                "location": instance.get("location"),
            }
        )
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
