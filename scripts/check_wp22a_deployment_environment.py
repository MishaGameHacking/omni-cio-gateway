from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Sequence


ENVIRONMENT_NAME = "wp22a-provider-production"
API_VERSION = "2022-11-28"


class DeploymentEnvironmentError(RuntimeError):
    pass


def validate_environment_snapshot(
    environment: Mapping[str, Any], branch_policies: Mapping[str, Any]
) -> None:
    if str(environment.get("name", "")) != ENVIRONMENT_NAME:
        raise DeploymentEnvironmentError("WP22A_DEPLOYMENT_ENVIRONMENT_NAME_INVALID")

    policy = environment.get("deployment_branch_policy")
    if not isinstance(policy, dict):
        raise DeploymentEnvironmentError("WP22A_DEPLOYMENT_BRANCH_POLICY_MISSING")
    if policy.get("custom_branch_policies") is not True:
        raise DeploymentEnvironmentError("WP22A_CUSTOM_BRANCH_POLICY_REQUIRED")
    if policy.get("protected_branches") is not False:
        raise DeploymentEnvironmentError("WP22A_PROTECTED_BRANCH_MODE_FORBIDDEN")

    raw_policies = branch_policies.get("branch_policies")
    if not isinstance(raw_policies, list):
        raise DeploymentEnvironmentError("WP22A_DEPLOYMENT_BRANCH_POLICIES_INVALID")
    if branch_policies.get("total_count") != 1 or len(raw_policies) != 1:
        raise DeploymentEnvironmentError("WP22A_EXACTLY_ONE_DEPLOYMENT_POLICY_REQUIRED")

    only = raw_policies[0]
    if not isinstance(only, dict):
        raise DeploymentEnvironmentError("WP22A_DEPLOYMENT_POLICY_INVALID")
    if str(only.get("name", "")) != "main":
        raise DeploymentEnvironmentError("WP22A_DEPLOYMENT_POLICY_MUST_BE_EXACT_MAIN")
    policy_type = str(only.get("type", "branch")).lower()
    if policy_type != "branch":
        raise DeploymentEnvironmentError("WP22A_DEPLOYMENT_POLICY_MUST_TARGET_BRANCH")


def _get_json(url: str, token: str) -> Mapping[str, Any]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "Omni-CIO-V10-WP22A/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DeploymentEnvironmentError("WP22A_DEPLOYMENT_ENVIRONMENT_API_FAILED") from exc
    if not isinstance(payload, dict):
        raise DeploymentEnvironmentError("WP22A_DEPLOYMENT_ENVIRONMENT_API_INVALID")
    return payload


def run() -> Mapping[str, Any]:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not repository or "/" not in repository:
        raise DeploymentEnvironmentError("WP22A_GITHUB_REPOSITORY_INVALID")
    if not token:
        raise DeploymentEnvironmentError("WP22A_GITHUB_TOKEN_MISSING")

    owner, repo = repository.split("/", 1)
    encoded_environment = urllib.parse.quote(ENVIRONMENT_NAME, safe="")
    base = f"https://api.github.com/repos/{owner}/{repo}/environments/{encoded_environment}"
    environment = _get_json(base, token)
    branch_policies = _get_json(f"{base}/deployment-branch-policies?per_page=100", token)
    validate_environment_snapshot(environment, branch_policies)
    return {
        "status": "PASS",
        "reason": "WP22A_DEPLOYMENT_ENVIRONMENT_MAIN_ONLY",
        "custom_branch_policy": True,
        "exact_main_only": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    try:
        result = run()
    except DeploymentEnvironmentError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
