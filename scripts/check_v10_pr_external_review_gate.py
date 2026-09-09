from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SONAR_CHECK_NAME = "SonarCloud Code Analysis"
SONAR_EXACT_HEAD = "Sonar exact-head"
EXTERNAL_GATE_FAILED = "External review gate failed"
STATUS_COMPLETED = "completed"
OUTPUT_KEY = "output"
ANNOTATIONS_COUNT_KEY = "annotations_count"
GITHUB_API_HOST = "api.github.com"
GITHUB_API_ROOT = f"https://{GITHUB_API_HOST}"
ZERO_NEW_ISSUES = re.compile(r"\[(\d+) New issues\]")
ZERO_HOTSPOTS = re.compile(r"\[(\d+) Security Hotspots\]")
API_VERSION = "2022-11-28"
DEFAULT_ATTEMPTS = 25
DEFAULT_DELAY_SECONDS = 5


class ReviewGateError(RuntimeError):
    """Raised when exact-head external review evidence cannot be trusted."""


def _is_github_api_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == GITHUB_API_HOST


def _github_json(url: str, token: str) -> Any:
    if not _is_github_api_url(url):
        raise ReviewGateError(
            "GitHub review-gate URL is outside the fixed HTTPS API host"
        )
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "omni-cio-green-checkpoint-gate",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:  # nosec B310 -- HTTPS host validated above
            return json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ReviewGateError(f"GitHub review-gate request failed: {exc}") from exc


def _check_runs_url(repository: str, head_sha: str) -> str:
    return (
        f"{GITHUB_API_ROOT}/repos/{repository}/commits/{head_sha}/check-runs"
        "?per_page=100&filter=latest"
    )


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

    for pattern, label, failure_label in (
        (ZERO_NEW_ISSUES, "new-issues metric", "new issues"),
        (ZERO_HOTSPOTS, "Security-Hotspots metric", "Security Hotspots"),
    ):
        try:
            value = _metric(summary, pattern, label)
        except ReviewGateError as exc:
            failures.append(str(exc))
        else:
            if value != 0:
                failures.append(
                    f"{SONAR_EXACT_HEAD} {failure_label} must be 0, got {value}"
                )

    annotations_count = output.get(ANNOTATIONS_COUNT_KEY)
    if annotations_count != 0:
        failures.append(
            f"{SONAR_EXACT_HEAD} annotations/new findings must be 0, "
            f"got {annotations_count!r}"
        )
    return failures


def _annotation_lines(run: dict[str, Any], token: str) -> list[str]:
    output = run.get(OUTPUT_KEY)
    output = output if isinstance(output, dict) else {}
    if output.get(ANNOTATIONS_COUNT_KEY) in (None, 0):
        return []
    annotations_url = output.get("annotations_url")
    if not isinstance(annotations_url, str) or not _is_github_api_url(annotations_url):
        return ["Sonar annotations URL missing or outside GitHub API"]
    payload = _github_json(f"{annotations_url}?per_page=100", token)
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


def _wait_for_sonar(repository: str, head_sha: str, token: str) -> dict[str, Any]:
    attempts = int(os.environ.get("V10_SONAR_GATE_ATTEMPTS", str(DEFAULT_ATTEMPTS)))
    delay = int(
        os.environ.get("V10_SONAR_GATE_DELAY_SECONDS", str(DEFAULT_DELAY_SECONDS))
    )
    for attempt in range(1, attempts + 1):
        payload = _github_json(_check_runs_url(repository, head_sha), token)
        run = _find_exact_sonar_run(payload, head_sha)
        if run is not None and run.get("status") == STATUS_COMPLETED:
            return run
        if attempt < attempts:
            time.sleep(delay)
    raise ReviewGateError(
        f"{SONAR_EXACT_HEAD} check did not complete within bounded wait"
    )


def _validated_environment() -> tuple[str, str, str] | None:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    head_sha = os.environ.get("EXPECTED_HEAD", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repository or re.fullmatch(r"[^/\s]+/[^/\s]+", repository) is None:
        print(f"{EXTERNAL_GATE_FAILED}: invalid GITHUB_REPOSITORY", file=sys.stderr)
        return None
    if re.fullmatch(r"[0-9a-f]{40}", head_sha) is None:
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
        run = _wait_for_sonar(repository, head_sha, token)
        failures = _validate_sonar_run(run)
        annotations = _annotation_lines(run, token) if failures else []
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
    print(
        "Sonar: Quality Gate success; new issues=0; Security Hotspots=0; annotations=0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
