from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
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
_CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
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


def _contract() -> tuple[frozenset[str], int]:
    try:
        payload = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        gate = payload["post_merge_gate"]
        names = gate["required_core_push_workflows"]
        minimum = gate["minimum_successful_push_workflows"]
    except (OSError, KeyError, TypeError, ValueError):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID") from None
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) or not name for name in names)
    ):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID")
    if not isinstance(minimum, int) or minimum < len(names):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_CONTRACT_INVALID")
    return frozenset(names), minimum


def _api_get(path: str, token: str) -> Any:
    if not path.startswith("/repos/") or "\\" in path:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_API_PATH_INVALID")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "omni-cio-v10-cloudflare-postmerge-gate",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    attempts = len(_RETRY_DELAYS) + 1
    for attempt in range(attempts):
        request = Request(f"{_API_BASE}{path}", headers=headers, method="GET")
        try:
            with _OPENER.open(request, timeout=30.0) as response:
                status = int(response.status)
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            status = int(exc.code)
            if status in _TRANSIENT_HTTP and attempt + 1 < attempts:
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            if status in {401, 403}:
                raise ReleaseGateStopped(
                    "CLOUDFLARE_POSTMERGE_GITHUB_AUTHORITY_INSUFFICIENT",
                    status=status,
                ) from None
            raise ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_GITHUB_HTTP_ERROR",
                status=status,
            ) from None
        except OSError:
            if attempt + 1 < attempts:
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            raise ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_GITHUB_NETWORK_ERROR"
            ) from None
        if status != 200:
            raise ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_GITHUB_STATUS_INVALID",
                status=status,
            )
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_GITHUB_RESPONSE_TOO_LARGE")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise ReleaseGateStopped(
                "CLOUDFLARE_POSTMERGE_GITHUB_JSON_INVALID"
            ) from None
    raise AssertionError("bounded GitHub API retry exhausted")


def _current_main_sha(repository: str, token: str) -> str:
    payload = _api_get(f"/repos/{repository}/commits/main", token)
    if not isinstance(payload, dict):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_MAIN_RESPONSE_INVALID")
    value = payload.get("sha")
    if not isinstance(value, str) or _SHA.fullmatch(value.lower()) is None:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_MAIN_RESPONSE_INVALID")
    return value.lower()


def _workflow_runs(
    repository: str, token: str, expected_sha: str
) -> list[dict[str, Any]]:
    query = urlencode(
        {
            "branch": "main",
            "event": "push",
            "head_sha": expected_sha,
            "per_page": "100",
            "exclude_pull_requests": "true",
        }
    )
    payload = _api_get(f"/repos/{repository}/actions/runs?{query}", token)
    if not isinstance(payload, dict) or not isinstance(
        payload.get("workflow_runs"), list
    ):
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUNS_RESPONSE_INVALID")
    rows: list[dict[str, Any]] = []
    for raw in payload["workflow_runs"]:
        if not isinstance(raw, dict):
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_RUN_INVALID")
        if (
            raw.get("head_sha") == expected_sha
            and raw.get("head_branch") == "main"
            and raw.get("event") == "push"
        ):
            rows.append(raw)
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


def wait_for_release_gate(
    expected_sha: str,
    *,
    environ: Mapping[str, str] | None = None,
    wait_seconds: int = _DEFAULT_WAIT_SECONDS,
    poll_seconds: int = _DEFAULT_POLL_SECONDS,
) -> int:
    if wait_seconds < 0 or wait_seconds > 1800:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_WAIT_INVALID")
    if poll_seconds < 1 or poll_seconds > 60:
        raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_POLL_INVALID")
    environment = os.environ if environ is None else environ
    sha = _expected_sha(expected_sha)
    repository = _repository(_required(environment, "GITHUB_REPOSITORY"))
    token = _required(environment, "GITHUB_TOKEN")
    required_names, minimum_successful = _contract()
    deadline = time.monotonic() + float(wait_seconds)
    while True:
        if _current_main_sha(repository, token) != sha:
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_MAIN_SUPERSEDED")
        ready, observed = _gate_state(
            _workflow_runs(repository, token, sha),
            required_names,
            minimum_successful,
        )
        if ready:
            if _current_main_sha(repository, token) != sha:
                raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_MAIN_SUPERSEDED")
            print(
                "CLOUDFLARE_POSTMERGE_GATE=READY "
                f"exact_sha={sha} push_workflows={observed}"
            )
            return observed
        if time.monotonic() >= deadline:
            raise ReleaseGateStopped("CLOUDFLARE_POSTMERGE_PUSH_WORKFLOWS_PENDING")
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
