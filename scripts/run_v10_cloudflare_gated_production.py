from __future__ import annotations

import argparse
import subprocess
import sys
import time
from typing import Any

import scripts.bootstrap_v10_cloudflare_builds as builds


_PRODUCTION_WORKER = "omni-cio-v10-web"
_PRODUCTION_BUILD_TOKEN_NAME = "omni-cio-v10-production-builds"
_PRODUCTION_TRIGGER_NAME = "Omni-CIO V10 production gated deploy"
_GATED_AUTOBUILD_SENTINEL_BRANCH = "__omni_cf_d_manual_only__"
_SOURCE_BRANCH = "main"
_BUILD_COMMAND = "npm run build"
_DEPLOY_COMMAND = "npm run cloudflare:deploy"
_NONTERMINAL_BUILD_STATUSES = frozenset({"queued", "initializing", "running"})
_TERMINAL_BUILD_OUTCOMES = frozenset(
    {"success", "fail", "skipped", "cancelled", "terminated"}
)
_CANCEL_CONFIRM_DELAYS = (1.0, 2.0, 4.0, 8.0, 15.0)


def _assert_exact_head(expected_sha: str) -> str:
    sha = builds._expected_sha(expected_sha)
    try:
        actual = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=builds._REPO_ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
            .lower()
        )
    except (OSError, subprocess.CalledProcessError):
        raise builds.BootstrapStopped("CLOUDFLARE_GIT_HEAD_UNAVAILABLE") from None
    if actual != sha:
        raise builds.BootstrapStopped("CLOUDFLARE_GIT_HEAD_MISMATCH")
    return sha


def _production_worker_tag(api: builds.CloudflareApi) -> str:
    rows = builds._list(
        api.request("GET", f"/accounts/{api.account_id}/workers/scripts"),
        "CLOUDFLARE_WORKERS_INVALID",
    )
    matches = [
        builds._object(row, "CLOUDFLARE_WORKER_INVALID")
        for row in rows
        if isinstance(row, dict) and row.get("id") == _PRODUCTION_WORKER
    ]
    if len(matches) != 1:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_WORKER_NOT_UNIQUE")
    return builds._worker_tag(matches[0].get("tag"))


def _ensure_production_build_token(
    api: builds.CloudflareApi,
    token_id: str,
) -> str:
    rows = builds._list(
        api.request("GET", f"/accounts/{api.account_id}/builds/tokens?per_page=200"),
        "CLOUDFLARE_BUILD_TOKENS_INVALID",
    )
    matches = [
        builds._object(row, "CLOUDFLARE_BUILD_TOKEN_INVALID")
        for row in rows
        if isinstance(row, dict)
        and row.get("build_token_name") == _PRODUCTION_BUILD_TOKEN_NAME
    ]
    if len(matches) > 1:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_TOKEN_NOT_UNIQUE")
    if matches:
        build_token_uuid = builds._build_token_uuid_with_authority(matches[0], token_id)
        print("CLOUDFLARE_PRODUCTION_BUILD_TOKEN=REUSED")
        return build_token_uuid
    result = builds._object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/tokens",
            body={
                "build_token_name": _PRODUCTION_BUILD_TOKEN_NAME,
                builds._BUILD_TOKEN_VALUE_FIELD: api.token,
                "cloudflare_token_id": token_id,
            },
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_PRODUCTION_BUILD_TOKEN_CREATE_INVALID",
    )
    build_token_uuid = builds._build_token_uuid_with_authority(result, token_id)
    print("CLOUDFLARE_PRODUCTION_BUILD_TOKEN=CREATED")
    return build_token_uuid


def _desired_trigger(connection_uuid: str, build_token_uuid: str) -> dict[str, Any]:
    return {
        "branch_excludes": [],
        "branch_includes": [_GATED_AUTOBUILD_SENTINEL_BRANCH],
        "build_caching_enabled": True,
        "build_command": _BUILD_COMMAND,
        "build_token_uuid": build_token_uuid,
        "deploy_command": _DEPLOY_COMMAND,
        "path_excludes": [],
        "path_includes": ["*"],
        "repo_connection_uuid": connection_uuid,
        "root_directory": "/",
        "trigger_name": _PRODUCTION_TRIGGER_NAME,
    }


def _validate_trigger(
    trigger: dict[str, Any],
    *,
    worker_tag: str,
    connection_uuid: str,
    desired: dict[str, Any],
) -> str:
    if trigger.get("external_script_id") != worker_tag:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_TRIGGER_WORKER_DRIFT")
    repo = builds._object(
        trigger.get("repo_connection"),
        "CLOUDFLARE_PRODUCTION_TRIGGER_REPO_INVALID",
    )
    expected_repo = {
        "repo_connection_uuid": connection_uuid,
        "provider_account_id": builds._GITHUB_OWNER_ID,
        "provider_account_name": builds._GITHUB_OWNER,
        "provider_type": "github",
        "repo_id": builds._GITHUB_REPO_ID,
        "repo_name": builds._GITHUB_REPO,
    }
    if any(repo.get(key) != value for key, value in expected_repo.items()):
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_TRIGGER_REPO_DRIFT")
    for key, value in desired.items():
        if key == "repo_connection_uuid":
            continue
        if trigger.get(key) != value:
            raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_TRIGGER_CONFIG_DRIFT")
    return builds._provider_uuid(
        trigger.get("trigger_uuid"),
        "CLOUDFLARE_TRIGGER_UUID_INVALID",
    )


def _existing_triggers(
    api: builds.CloudflareApi,
    worker_tag: str,
) -> list[dict[str, Any]]:
    rows = builds._list(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/builds/workers/{worker_tag}/triggers",
        ),
        "CLOUDFLARE_TRIGGERS_INVALID",
    )
    return [builds._object(row, "CLOUDFLARE_TRIGGER_INVALID") for row in rows]


def _stale_owned_trigger_uuid(
    api: builds.CloudflareApi,
    *,
    worker_tag: str,
    connection_uuid: str,
    desired: dict[str, Any],
) -> str | None:
    rows = _existing_triggers(api, worker_tag)
    if not rows:
        return None
    if len(rows) != 1 or rows[0].get("trigger_name") != _PRODUCTION_TRIGGER_NAME:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_AUTODEPLOY_FORBIDDEN")
    return _validate_trigger(
        rows[0],
        worker_tag=worker_tag,
        connection_uuid=connection_uuid,
        desired=desired,
    )


def _create_trigger(
    api: builds.CloudflareApi,
    *,
    worker_tag: str,
    connection_uuid: str,
    build_token_uuid: str,
) -> str:
    desired = _desired_trigger(connection_uuid, build_token_uuid)
    if _existing_triggers(api, worker_tag):
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_TRIGGER_RACE")
    result = builds._object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/triggers",
            body={**desired, "external_script_id": worker_tag},
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_PRODUCTION_TRIGGER_CREATE_INVALID",
    )
    trigger_uuid = _validate_trigger(
        result,
        worker_tag=worker_tag,
        connection_uuid=connection_uuid,
        desired=desired,
    )
    print("CLOUDFLARE_PRODUCTION_GATED_TRIGGER=CREATED")
    return trigger_uuid


def _start_build(
    api: builds.CloudflareApi,
    *,
    trigger_uuid: str,
    expected_sha: str,
) -> str:
    result = builds._object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/triggers/{trigger_uuid}/builds",
            body={"branch": _SOURCE_BRANCH, "commit_hash": expected_sha},
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_PRODUCTION_BUILD_CREATE_INVALID",
    )
    build_uuid = builds._provider_uuid(
        result.get("build_uuid"),
        "CLOUDFLARE_BUILD_UUID_INVALID",
    )
    print("CLOUDFLARE_PRODUCTION_BUILD_SOURCE=GATED_MANUAL_EXACT_MAIN")
    return build_uuid


def _assert_build_identity(row: dict[str, Any], expected_sha: str) -> None:
    if builds._build_commit_hash(row, required=True) != expected_sha:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_SHA_MISMATCH")
    trigger = builds._build_trigger_metadata(row, required=True)
    assert trigger is not None
    expected = {
        "commit_hash": expected_sha,
        "branch": _SOURCE_BRANCH,
        "build_command": _BUILD_COMMAND,
        "deploy_command": _DEPLOY_COMMAND,
    }
    if any(trigger.get(key) != value for key, value in expected.items()):
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_IDENTITY_DRIFT")


def _build_status(api: builds.CloudflareApi, build_uuid: str) -> dict[str, Any]:
    return builds._object(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/builds/builds/{build_uuid}",
        ),
        "CLOUDFLARE_BUILD_STATUS_INVALID",
    )


def _build_is_terminal(row: dict[str, Any]) -> bool:
    outcome = row.get("build_outcome")
    if outcome in _TERMINAL_BUILD_OUTCOMES:
        return True
    if outcome is not None:
        raise builds.BootstrapStopped("CLOUDFLARE_BUILD_OUTCOME_INVALID")
    status = row.get("status")
    if status == "stopped":
        return True
    if status not in _NONTERMINAL_BUILD_STATUSES:
        raise builds.BootstrapStopped("CLOUDFLARE_BUILD_STATUS_INVALID")
    return False


def _wait_build(api: builds.CloudflareApi, build_uuid: str, expected_sha: str) -> None:
    deadline = time.monotonic() + 1200.0
    while True:
        result = _build_status(api, build_uuid)
        commit_hash = builds._build_commit_hash(result)
        if commit_hash is not None and commit_hash != expected_sha:
            raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_SHA_MISMATCH")
        outcome = result.get("build_outcome")
        if outcome == "success":
            _assert_build_identity(result, expected_sha)
            print("CLOUDFLARE_PRODUCTION_BUILD=SUCCESS")
            return
        if outcome in builds._TERMINAL_BUILD_FAILURES:
            diagnostic = builds._safe_build_failure_diagnostic(api, build_uuid)
            if diagnostic in builds._ACTIONABLE_BUILD_FAILURES:
                raise builds.BootstrapStopped(diagnostic)
            raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_FAILED")
        if result.get("status") == "stopped":
            raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_OUTCOME_MISSING")
        if time.monotonic() >= deadline:
            raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_TIMEOUT")
        time.sleep(10.0)


def _wait_cancel_terminal(
    api: builds.CloudflareApi,
    build_uuid: str,
) -> dict[str, Any]:
    attempts = len(_CANCEL_CONFIRM_DELAYS) + 1
    for attempt in range(attempts):
        current = _build_status(api, build_uuid)
        if _build_is_terminal(current):
            return current
        if attempt + 1 >= attempts:
            raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_CANCEL_RACE")
        time.sleep(_CANCEL_CONFIRM_DELAYS[attempt])
    raise AssertionError("bounded production build cancellation confirmation exhausted")


def _cancel_if_nonterminal(
    api: builds.CloudflareApi,
    build_uuid: str | None,
) -> dict[str, Any] | None:
    if build_uuid is None:
        return None
    current = _build_status(api, build_uuid)
    if _build_is_terminal(current):
        return current
    path = f"/accounts/{api.account_id}/builds/builds/{build_uuid}/cancel"
    try:
        api.request("PUT", path)
    except builds.BootstrapStopped as exc:
        if exc.code != "CLOUDFLARE_API_HTTP_ERROR" or exc.status not in {400, 409}:
            raise
    return _wait_cancel_terminal(api, build_uuid)


def _assert_stale_build_safely_terminal(row: dict[str, Any]) -> None:
    outcome = row.get("build_outcome")
    if outcome == "success":
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_STALE_BUILD_SUCCESS_RACE")
    if outcome not in builds._TERMINAL_BUILD_FAILURES:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_PRODUCTION_STALE_BUILD_OUTCOME_UNCONFIRMED"
        )


def _cancel_nonterminal_builds(
    api: builds.CloudflareApi,
    worker_tag: str,
) -> int:
    cancelled = 0
    for row in builds._builds_for_worker(api, worker_tag):
        if _build_is_terminal(row):
            continue
        build_uuid = builds._provider_uuid(
            row.get("build_uuid"),
            "CLOUDFLARE_BUILD_UUID_INVALID",
        )
        terminal = _cancel_if_nonterminal(api, build_uuid)
        if terminal is None:
            raise AssertionError("stale production build UUID unexpectedly absent")
        _assert_stale_build_safely_terminal(terminal)
        cancelled += 1
    if cancelled:
        print(
            "CLOUDFLARE_PRODUCTION_STALE_BUILDS=QUARANTINED "
            f"cancelled_builds={cancelled}"
        )
    return cancelled


def _prepare_authority(
    api: builds.CloudflareApi,
) -> tuple[str, str, str]:
    api.request("GET", f"/accounts/{api.account_id}/builds/account/limits")
    print("CLOUDFLARE_BUILDS_API=READY")
    token_id = builds._verify_token(api)
    connection_uuid = builds._ensure_repo_connection(api)
    build_token_uuid = _ensure_production_build_token(api, token_id)
    worker_tag = _production_worker_tag(api)
    return worker_tag, connection_uuid, build_token_uuid


def _quarantine_provider_activity(
    api: builds.CloudflareApi,
    *,
    worker_tag: str,
    connection_uuid: str,
    build_token_uuid: str,
) -> tuple[int, int]:
    desired = _desired_trigger(connection_uuid, build_token_uuid)
    trigger_uuid = _stale_owned_trigger_uuid(
        api,
        worker_tag=worker_tag,
        connection_uuid=connection_uuid,
        desired=desired,
    )
    cancelled = _cancel_nonterminal_builds(api, worker_tag)
    deleted = 0
    if trigger_uuid is not None:
        _delete_trigger(api, trigger_uuid)
        deleted = 1
    print(
        "CLOUDFLARE_PRODUCTION_PROVIDER_ACTIVITY=QUARANTINED "
        f"cancelled_builds={cancelled} deleted_triggers={deleted}"
    )
    return cancelled, deleted


def _delete_trigger(api: builds.CloudflareApi, trigger_uuid: str | None) -> None:
    if trigger_uuid is None:
        return
    api.request(
        "DELETE",
        f"/accounts/{api.account_id}/builds/triggers/{trigger_uuid}",
    )
    print("CLOUDFLARE_PRODUCTION_GATED_TRIGGER=QUARANTINED")


def quarantine(expected_sha: str) -> tuple[int, int]:
    _assert_exact_head(expected_sha)
    token = builds._required_env("CLOUDFLARE_API_TOKEN")
    account_id = builds._required_env("CLOUDFLARE_ACCOUNT_ID")
    api = builds.CloudflareApi(account_id, token)
    worker_tag, connection_uuid, build_token_uuid = _prepare_authority(api)
    return _quarantine_provider_activity(
        api,
        worker_tag=worker_tag,
        connection_uuid=connection_uuid,
        build_token_uuid=build_token_uuid,
    )


def run(expected_sha: str) -> str:
    sha = _assert_exact_head(expected_sha)
    token = builds._required_env("CLOUDFLARE_API_TOKEN")
    account_id = builds._required_env("CLOUDFLARE_ACCOUNT_ID")
    api = builds.CloudflareApi(account_id, token)

    trigger_uuid: str | None = None
    build_uuid: str | None = None
    primary: builds.BootstrapStopped | None = None
    try:
        worker_tag, connection_uuid, build_token_uuid = _prepare_authority(api)
        _quarantine_provider_activity(
            api,
            worker_tag=worker_tag,
            connection_uuid=connection_uuid,
            build_token_uuid=build_token_uuid,
        )
        trigger_uuid = _create_trigger(
            api,
            worker_tag=worker_tag,
            connection_uuid=connection_uuid,
            build_token_uuid=build_token_uuid,
        )
        build_uuid = _start_build(
            api,
            trigger_uuid=trigger_uuid,
            expected_sha=sha,
        )
        _wait_build(api, build_uuid, sha)
    except builds.BootstrapStopped as exc:
        primary = exc

    cleanup: builds.BootstrapStopped | None = None
    try:
        _cancel_if_nonterminal(api, build_uuid)
        _delete_trigger(api, trigger_uuid)
    except builds.BootstrapStopped as exc:
        cleanup = exc

    if cleanup is not None:
        if primary is not None:
            print(f"CLOUDFLARE_PRODUCTION_PRIMARY_FAILURE={primary.code}")
        raise builds.BootstrapStopped(
            "CLOUDFLARE_PRODUCTION_GATED_CLEANUP_FAILED",
            status=cleanup.status,
        ) from None
    if primary is not None:
        raise primary
    if build_uuid is None:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_RESULT_MISSING")
    builds._write_output("cloudflare_build_uuid", build_uuid)
    print("CLOUDFLARE_CF_D_PRODUCTION_BUILD=DEPLOYED")
    return build_uuid


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--quarantine-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.quarantine_only:
            quarantine(args.expected_sha)
            print("CLOUDFLARE_CF_D_PRODUCTION_QUARANTINE=READY")
        else:
            run(args.expected_sha)
    except builds.BootstrapStopped as exc:
        fields = ["CLOUDFLARE_CF_D_PRODUCTION_BUILD=STOPPED", f"code={exc.code}"]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
