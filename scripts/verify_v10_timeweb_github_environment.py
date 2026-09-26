from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os
import re
import sys
import time
from typing import Any, NoReturn
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, OpenerDirector, Request, build_opener


API_BASE = "https://api.github.com"
API_VERSION = "2026-03-10"
ENVIRONMENT_NAME = "timeweb-synthetic"
PRODUCTION_ENVIRONMENT_NAME = "timeweb-production"
_ALLOWED_ENVIRONMENT_NAMES = frozenset({ENVIRONMENT_NAME, PRODUCTION_ENVIRONMENT_NAME})
EXPECTED_BRANCH_PATTERN = "main"
MAX_RESPONSE_BYTES = 1024 * 1024
_RETRY_DELAYS_SECONDS = (1.0, 2.0)
_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 502, 503, 504})
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GITHUB_BINDING = "GITHUB_" + "TOKEN"
Sleep = Callable[[float], None]


class EnvironmentGateError(RuntimeError):
    pass


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler())


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EnvironmentGateError(code)
    return value


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_INPUT_MISSING")
    return value


def _repository_slug(value: str) -> str:
    if not _REPOSITORY_RE.fullmatch(value):
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_REPOSITORY_INVALID")
    return value


def _open_once(
    request: Request,
    opener: OpenerDirector | Any,
) -> tuple[int, bytes]:
    with opener.open(request, timeout=15.0) as response:
        return int(response.status), response.read(MAX_RESPONSE_BYTES + 1)


def _retry_available(attempt: int) -> bool:
    return attempt < len(_RETRY_DELAYS_SECONDS)


def _raise_http_failure(status: int) -> NoReturn:
    fixed_codes = {
        401: "TIMEWEB_GITHUB_ENVIRONMENT_GATE_AUTHENTICATION_FAILED",
        403: "TIMEWEB_GITHUB_ENVIRONMENT_GATE_PERMISSION_DENIED",
        404: "TIMEWEB_GITHUB_ENVIRONMENT_GATE_NOT_FOUND",
    }
    if status in fixed_codes:
        raise EnvironmentGateError(fixed_codes[status]) from None
    if status in _TRANSIENT_HTTP_STATUSES:
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_TRANSIENT_EXHAUSTED"
        ) from None
    raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_HTTP_FAILURE") from None


def _open_with_retries(
    request: Request,
    *,
    opener: OpenerDirector | Any,
    sleeper: Sleep,
) -> tuple[int, bytes]:
    attempts = len(_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        try:
            return _open_once(request, opener)
        except HTTPError as exc:
            status = int(exc.code)
            if status in _TRANSIENT_HTTP_STATUSES and _retry_available(attempt):
                sleeper(_RETRY_DELAYS_SECONDS[attempt])
                continue
            _raise_http_failure(status)
        except OSError:
            if not _retry_available(attempt):
                raise EnvironmentGateError(
                    "TIMEWEB_GITHUB_ENVIRONMENT_GATE_TRANSPORT_FAILURE"
                ) from None
            sleeper(_RETRY_DELAYS_SECONDS[attempt])
    raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_RETRY_STATE_INVALID")


def _decode_response(status: int, raw: bytes) -> dict[str, Any]:
    if status != 200:
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_HTTP_FAILURE")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_RESPONSE_TOO_LARGE")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_RESPONSE_INVALID"
        ) from None
    return _mapping(payload, "TIMEWEB_GITHUB_ENVIRONMENT_GATE_RESPONSE_INVALID")


def _request_json(
    path: str,
    token: str,
    *,
    opener: OpenerDirector | Any | None = None,
    sleeper: Sleep = time.sleep,
) -> dict[str, Any]:
    if not path.startswith("/repos/"):
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_PATH_INVALID")

    request = Request(
        API_BASE + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "omni-cio-v10-timeweb-environment-gate",
            "X-GitHub-Api-Version": API_VERSION,
        },
        method="GET",
    )
    status, raw = _open_with_retries(
        request,
        opener=opener or _NO_REDIRECT_OPENER,
        sleeper=sleeper,
    )
    return _decode_response(status, raw)


def _validate_environment(payload: dict[str, Any], *, environment_name: str) -> None:
    if payload.get("name") != environment_name:
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_NAME_MISMATCH")

    policy = _mapping(
        payload.get("deployment_branch_policy"),
        "TIMEWEB_GITHUB_ENVIRONMENT_GATE_SELECTION_MODE_INVALID",
    )
    if policy.get("protected_branches") is not False:
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_SELECTION_MODE_INVALID"
        )
    if policy.get("custom_branch_policies") is not True:
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_SELECTION_MODE_INVALID"
        )

    protection_rules = payload.get("protection_rules")
    if not isinstance(protection_rules, list):
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_PROTECTION_RULES_INVALID"
        )
    if not any(
        isinstance(rule, dict) and rule.get("type") == "branch_policy"
        for rule in protection_rules
    ):
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_BRANCH_POLICY_MISSING"
        )


def _validate_branch_policies(payload: dict[str, Any]) -> None:
    policies = payload.get("branch_policies")
    if payload.get("total_count") != 1 or not isinstance(policies, list):
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_COUNT_INVALID"
        )
    if len(policies) != 1:
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_COUNT_INVALID"
        )

    policy = _mapping(
        policies[0],
        "TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_INVALID",
    )
    if policy.get("name") != EXPECTED_BRANCH_PATTERN:
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_PATTERN_INVALID")

    # GitHub's documented list-response example omits the policy type. When it is
    # omitted, the provider job's environment protection on refs/heads/main remains
    # the authoritative branch-vs-tag enforcement boundary.
    policy_type = policy.get("type")
    if policy_type is not None and policy_type != "branch":
        raise EnvironmentGateError(
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_TYPE_INVALID"
        )


def verify_environment_policy(
    token: str,
    repository: str,
    *,
    environment_name: str = ENVIRONMENT_NAME,
    opener: OpenerDirector | Any | None = None,
    sleeper: Sleep = time.sleep,
) -> None:
    if environment_name not in _ALLOWED_ENVIRONMENT_NAMES:
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_NAME_INVALID")
    slug = _repository_slug(repository)
    encoded_environment = quote(environment_name, safe="")
    base = f"/repos/{slug}/environments/{encoded_environment}"
    active_opener = opener or _NO_REDIRECT_OPENER

    environment = _request_json(
        base,
        token,
        opener=active_opener,
        sleeper=sleeper,
    )
    _validate_environment(environment, environment_name=environment_name)

    policies = _request_json(
        base + "/deployment-branch-policies?per_page=100&page=1",
        token,
        opener=active_opener,
        sleeper=sleeper,
    )
    _validate_branch_policies(policies)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment-name",
        choices=tuple(sorted(_ALLOWED_ENVIRONMENT_NAMES)),
        default=ENVIRONMENT_NAME,
    )
    args = parser.parse_args()
    try:
        repository = _required_environment("GITHUB_REPOSITORY")
        token = _required_environment(_GITHUB_BINDING)
        verify_environment_policy(
            token,
            repository,
            environment_name=args.environment_name,
        )
    except EnvironmentGateError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
