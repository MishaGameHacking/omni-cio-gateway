from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Any

import scripts.bootstrap_v10_cloudflare_builds as builds


_TERMINAL_BUILD_OUTCOMES = frozenset(
    {"success", "fail", "skipped", "cancelled", "terminated"}
)
_NONTERMINAL_BUILD_STATUSES = frozenset({"queued", "initializing", "running"})


def _assert_exact_head(expected_sha: str) -> str:
    sha = builds._expected_sha(expected_sha)
    try:
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=builds._REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip().lower()
    except (OSError, subprocess.CalledProcessError):
        raise builds.BootstrapStopped("CLOUDFLARE_GIT_HEAD_UNAVAILABLE") from None
    if actual != sha:
        raise builds.BootstrapStopped("CLOUDFLARE_GIT_HEAD_MISMATCH")
    return sha


def _staging_worker_tag(api: builds.CloudflareApi) -> str | None:
    rows = builds._list(
        api.request("GET", f"/accounts/{api.account_id}/workers/scripts"),
        "CLOUDFLARE_WORKERS_INVALID",
    )
    matches = [
        builds._object(row, "CLOUDFLARE_WORKER_INVALID")
        for row in rows
        if isinstance(row, dict) and row.get("id") == builds._STAGING_WORKER
    ]
    if len(matches) > 1:
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_WORKER_NOT_UNIQUE")
    if not matches:
        return None
    return builds._worker_tag(matches[0].get("tag"))


def _validate_repo_authority(trigger: dict[str, Any], worker_tag: str) -> str:
    if trigger.get("external_script_id") != worker_tag:
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_TRIGGER_WORKER_DRIFT")
    repo = builds._object(
        trigger.get("repo_connection"),
        "CLOUDFLARE_TRIGGER_REPO_CONNECTION_INVALID",
    )
    expected_repo = {
        "provider_account_id": builds._GITHUB_OWNER_ID,
        "provider_account_name": builds._GITHUB_OWNER,
        "provider_type": "github",
        "repo_id": builds._GITHUB_REPO_ID,
        "repo_name": builds._GITHUB_REPO,
    }
    if any(repo.get(key) != value for key, value in expected_repo.items()):
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_TRIGGER_REPO_AUTHORITY_DRIFT")
    return builds._provider_uuid(
        trigger.get("trigger_uuid"),
        "CLOUDFLARE_TRIGGER_UUID_INVALID",
    )


def _staging_triggers(
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


def remove_staging_triggers(api: builds.CloudflareApi, worker_tag: str) -> int:
    triggers = _staging_triggers(api, worker_tag)
    trigger_uuids = [
        _validate_repo_authority(trigger, worker_tag) for trigger in triggers
    ]
    for trigger_uuid in trigger_uuids:
        api.request(
            "DELETE",
            f"/accounts/{api.account_id}/builds/triggers/{trigger_uuid}",
        )
    return len(trigger_uuids)


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


def _cancel_nonterminal_build(
    api: builds.CloudflareApi,
    build_uuid: str,
) -> None:
    path = f"/accounts/{api.account_id}/builds/builds/{build_uuid}/cancel"
    try:
        api.request("PUT", path)
        return
    except builds.BootstrapStopped as exc:
        if exc.code != "CLOUDFLARE_API_HTTP_ERROR" or exc.status not in {400, 409}:
            raise
    current = builds._object(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/builds/builds/{build_uuid}",
        ),
        "CLOUDFLARE_BUILD_STATUS_INVALID",
    )
    if not _build_is_terminal(current):
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_BUILD_CANCEL_RACE")


def _cancel_staging_builds(api: builds.CloudflareApi, worker_tag: str) -> int:
    cancelled = 0
    for row in builds._builds_for_worker(api, worker_tag):
        if _build_is_terminal(row):
            continue
        build_uuid = builds._provider_uuid(
            row.get("build_uuid"),
            "CLOUDFLARE_BUILD_UUID_INVALID",
        )
        _cancel_nonterminal_build(api, build_uuid)
        cancelled += 1
    return cancelled


def quarantine_staging_autobuild(
    api: builds.CloudflareApi,
    *,
    expected_sha: str,
    verify_head: bool = True,
) -> tuple[int, int]:
    if verify_head:
        _assert_exact_head(expected_sha)
    else:
        builds._expected_sha(expected_sha)
    worker_tag = _staging_worker_tag(api)
    if worker_tag is None:
        print("CLOUDFLARE_STAGING_AUTOBUILD=ABSENT")
        return 0, 0

    deleted = remove_staging_triggers(api, worker_tag)
    cancelled = _cancel_staging_builds(api, worker_tag)

    print(
        "CLOUDFLARE_STAGING_AUTOBUILD=QUARANTINED "
        f"cancelled_builds={cancelled} deleted_triggers={deleted}"
    )
    return cancelled, deleted


def run(expected_sha: str) -> None:
    _assert_exact_head(expected_sha)
    token = builds._required_env("CLOUDFLARE_API_TOKEN")
    account_id = builds._required_env("CLOUDFLARE_ACCOUNT_ID")
    api = builds.CloudflareApi(account_id, token)
    api.request("GET", f"/accounts/{api.account_id}/builds/account/limits")
    builds._verify_token(api)
    quarantine_staging_autobuild(api, expected_sha=expected_sha, verify_head=False)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args.expected_sha)
    except builds.BootstrapStopped as exc:
        fields = ["CLOUDFLARE_STAGING_AUTOBUILD=BLOCKED", f"code={exc.code}"]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
