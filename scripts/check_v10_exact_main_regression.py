from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import os
import re
import sys
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


GITHUB_API_BASE = "https://api.github.com"
REGRESSION_WORKFLOW = "regression-shield.yml"
REQUIRED_JOBS = (
    "Quality, contracts and coverage",
    "Dependency, code and secret security",
)
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/"
    r"[A-Za-z0-9._-]{1,100}$"
)
_MAX_RESPONSE_BYTES = 1_048_576


class HttpResponse(Protocol):
    status: int

    def __enter__(self) -> "HttpResponse": ...

    def __exit__(self, *args: object) -> None: ...

    def read(self, amount: int = -1) -> bytes: ...


OpenUrl = Callable[..., HttpResponse]


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects())


class RegressionStopped(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        suffix = f" status={status}" if status is not None else ""
        super().__init__(f"{code}{suffix}")


def _required_env(name: str, env: Mapping[str, str]) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise RegressionStopped(f"{name}_REQUIRED")
    return value


def _repository(value: str) -> tuple[str, str]:
    if _REPOSITORY_PATTERN.fullmatch(value) is None:
        raise RegressionStopped("GITHUB_REPOSITORY_INVALID")
    owner, repository = value.split("/", 1)
    return quote(owner, safe=""), quote(repository, safe="")


def _expected_sha(value: str) -> str:
    normalized = value.strip().lower()
    if _SHA_PATTERN.fullmatch(normalized) is None:
        raise RegressionStopped("EXPECTED_MAIN_SHA_INVALID")
    return normalized


def _json_object(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegressionStopped(code)
    return value


def _json_list(value: Any, code: str) -> list[Any]:
    if not isinstance(value, list):
        raise RegressionStopped(code)
    return value


def _request_json(
    url: str,
    token: str,
    *,
    opener: OpenUrl | None = None,
) -> dict[str, Any]:
    if not url.startswith(f"{GITHUB_API_BASE}/repos/"):
        raise RegressionStopped("GITHUB_API_URL_INVALID")
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "omni-cio-v10-exact-main-regression",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    open_url = _NO_REDIRECT_OPENER.open if opener is None else opener
    try:
        with open_url(request, timeout=30.0) as response:
            status = int(response.status)
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        status = int(exc.code)
        if 300 <= status < 400:
            raise RegressionStopped(
                "GITHUB_ACTIONS_REDIRECT_FORBIDDEN",
                status=status,
            ) from None
        if status in {401, 403}:
            raise RegressionStopped(
                "GITHUB_ACTIONS_READ_FORBIDDEN",
                status=status,
            ) from None
        raise RegressionStopped(
            "GITHUB_ACTIONS_HTTP_ERROR",
            status=status,
        ) from None
    except (URLError, TimeoutError, OSError):
        raise RegressionStopped("GITHUB_ACTIONS_NETWORK_ERROR") from None
    if status != 200:
        raise RegressionStopped(
            "GITHUB_ACTIONS_UNEXPECTED_STATUS",
            status=status,
        )
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise RegressionStopped("GITHUB_ACTIONS_RESPONSE_TOO_LARGE")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RegressionStopped("GITHUB_ACTIONS_JSON_INVALID") from None
    return _json_object(payload, "GITHUB_ACTIONS_RESPONSE_INVALID")


def verify_exact_main_regression(
    *,
    env: Mapping[str, str] | None = None,
    opener: OpenUrl | None = None,
) -> int:
    source = os.environ if env is None else env
    owner, repository = _repository(_required_env("GITHUB_REPOSITORY", source))
    token = _required_env("GITHUB_TOKEN", source)
    expected_sha = _expected_sha(_required_env("EXPECTED_MAIN_SHA", source))

    query = urlencode(
        {
            "branch": "main",
            "event": "push",
            "head_sha": expected_sha,
            "per_page": 10,
        }
    )
    runs_url = (
        f"{GITHUB_API_BASE}/repos/{owner}/{repository}/actions/workflows/"
        f"{REGRESSION_WORKFLOW}/runs?{query}"
    )
    runs_payload = _request_json(runs_url, token, opener=opener)
    runs = [
        _json_object(item, "REGRESSION_SHIELD_RUN_INVALID")
        for item in _json_list(
            runs_payload.get("workflow_runs"),
            "REGRESSION_SHIELD_RUNS_INVALID",
        )
    ]
    if len(runs) != 1:
        raise RegressionStopped("REGRESSION_SHIELD_RUN_NOT_UNIQUE")
    run = runs[0]
    if (
        run.get("head_sha") != expected_sha
        or run.get("head_branch") != "main"
        or run.get("event") != "push"
        or run.get("path") != f".github/workflows/{REGRESSION_WORKFLOW}"
    ):
        raise RegressionStopped("REGRESSION_SHIELD_RUN_DRIFT")
    if run.get("status") != "completed":
        raise RegressionStopped("REGRESSION_SHIELD_NOT_COMPLETED")
    if run.get("conclusion") != "success":
        raise RegressionStopped("REGRESSION_SHIELD_NOT_GREEN")
    run_id = run.get("id")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise RegressionStopped("REGRESSION_SHIELD_RUN_ID_INVALID")

    jobs_query = urlencode({"filter": "latest", "per_page": 100})
    jobs_url = (
        f"{GITHUB_API_BASE}/repos/{owner}/{repository}/actions/runs/"
        f"{run_id}/jobs?{jobs_query}"
    )
    jobs_payload = _request_json(jobs_url, token, opener=opener)
    jobs = [
        _json_object(item, "REGRESSION_SHIELD_JOB_INVALID")
        for item in _json_list(
            jobs_payload.get("jobs"),
            "REGRESSION_SHIELD_JOBS_INVALID",
        )
    ]
    for required_name in REQUIRED_JOBS:
        matches = [job for job in jobs if job.get("name") == required_name]
        if len(matches) != 1:
            raise RegressionStopped("REGRESSION_SHIELD_REQUIRED_JOB_NOT_UNIQUE")
        job = matches[0]
        if job.get("status") != "completed":
            raise RegressionStopped("REGRESSION_SHIELD_REQUIRED_JOB_NOT_COMPLETED")
        if job.get("conclusion") != "success":
            raise RegressionStopped("REGRESSION_SHIELD_REQUIRED_JOB_NOT_GREEN")

    print(f"EXACT_MAIN_REGRESSION=PASS run_id={run_id} head_sha={expected_sha}")
    for required_name in REQUIRED_JOBS:
        print(f"EXACT_MAIN_REGRESSION_JOB=PASS name={required_name}")
    return run_id


def main() -> int:
    try:
        verify_exact_main_regression()
    except RegressionStopped as exc:
        print(f"::error::{exc.code}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
