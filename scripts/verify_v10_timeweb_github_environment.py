from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_BASE = "https://api.github.com"
API_VERSION = "2026-03-10"
ENVIRONMENT_NAME = "timeweb-synthetic"
EXPECTED_BRANCH_PATTERN = "main"
MAX_RESPONSE_BYTES = 1_048_576
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 15.0
_TRANSIENT_HTTP = {429, 500, 502, 503, 504}
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GITHUB_BINDING = "GITHUB_" + "TOKEN"


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
    ) -> None:
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


def _request_json(
    path: str,
    token: str,
    *,
    opener: object = _NO_REDIRECT_OPENER,
    sleeper: object = time.sleep,
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

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                if getattr(response, "status", 0) != 200:
                    raise EnvironmentGateError(
                        "TIMEWEB_GITHUB_ENVIRONMENT_GATE_HTTP_FAILURE"
                    )
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise EnvironmentGateError(
                        "TIMEWEB_GITHUB_ENVIRONMENT_GATE_RESPONSE_TOO_LARGE"
                    )
        except HTTPError as exc:
            if exc.code in _TRANSIENT_HTTP and attempt < MAX_ATTEMPTS:
                sleeper(float(attempt))
                continue
            if exc.code in {401, 403, 404}:
                raise EnvironmentGateError(
                    "TIMEWEB_GITHUB_ENVIRONMENT_GATE_UNAVAILABLE"
                ) from None
            if exc.code in _TRANSIENT_HTTP:
                raise EnvironmentGateError(
                    "TIMEWEB_GITHUB_ENVIRONMENT_GATE_TRANSIENT_EXHAUSTED"
                ) from None
            raise EnvironmentGateError(
                "TIMEWEB_GITHUB_ENVIRONMENT_GATE_HTTP_FAILURE"
            ) from None
        except URLError:
            if attempt < MAX_ATTEMPTS:
                sleeper(float(attempt))
                continue
            raise EnvironmentGateError(
                "TIMEWEB_GITHUB_ENVIRONMENT_GATE_TRANSPORT_FAILURE"
            ) from None

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise EnvironmentGateError(
                "TIMEWEB_GITHUB_ENVIRONMENT_GATE_RESPONSE_INVALID"
            ) from None
        return _mapping(payload, "TIMEWEB_GITHUB_ENVIRONMENT_GATE_RESPONSE_INVALID")

    raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_TRANSIENT_EXHAUSTED")


def _validate_environment(payload: dict[str, Any]) -> None:
    if payload.get("name") != ENVIRONMENT_NAME:
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
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_COUNT_INVALID")
    if len(policies) != 1:
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_COUNT_INVALID")

    policy = _mapping(
        policies[0],
        "TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_INVALID",
    )
    if policy.get("name") != EXPECTED_BRANCH_PATTERN:
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_PATTERN_INVALID")

    policy_type = policy.get("type")
    if policy_type is not None and policy_type != "branch":
        raise EnvironmentGateError("TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_TYPE_INVALID")


def verify_environment_policy(
    token: str,
    repository: str,
    *,
    opener: object = _NO_REDIRECT_OPENER,
    sleeper: object = time.sleep,
) -> None:
    slug = _repository_slug(repository)
    encoded_environment = quote(ENVIRONMENT_NAME, safe="")
    base = f"/repos/{slug}/environments/{encoded_environment}"

    environment = _request_json(
        base,
        token,
        opener=opener,
        sleeper=sleeper,
    )
    _validate_environment(environment)

    policies = _request_json(
        base + "/deployment-branch-policies?per_page=100&page=1",
        token,
        opener=opener,
        sleeper=sleeper,
    )
    _validate_branch_policies(policies)


def main() -> int:
    try:
        repository = _required_environment("GITHUB_REPOSITORY")
        token = _required_environment(_GITHUB_BINDING)
        verify_environment_policy(token, repository)
    except EnvironmentGateError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
