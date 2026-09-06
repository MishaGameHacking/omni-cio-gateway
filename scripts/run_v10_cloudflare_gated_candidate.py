from __future__ import annotations

import argparse
from contextlib import contextmanager
import subprocess
import sys
from typing import Iterator

import scripts.bootstrap_v10_cloudflare_builds as builds
from scripts.probe_v10_cloudflare_staging_runtime_secret import (
    _runtime_secret_present,
)
from scripts.quarantine_v10_cloudflare_staging_trigger import (
    quarantine_staging_autobuild,
)
from scripts.sync_v10_cloudflare_cf_d_bootstrap_origin import (
    sync_bootstrap_origin_custody,
)


_GATED_AUTOBUILD_SENTINEL_BRANCH = "__omni_cf_c_manual_only__"
_ALLOWED_SOURCE_BRANCHES = frozenset({"system/cloudflare-public-product", "main"})


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


def _source_branch(value: str) -> str:
    branch = value.strip()
    if branch not in _ALLOWED_SOURCE_BRANCHES:
        raise builds.BootstrapStopped("CLOUDFLARE_CANDIDATE_SOURCE_BRANCH_INVALID")
    return branch


@contextmanager
def _candidate_source_branch(branch: str) -> Iterator[None]:
    """Bind the accepted legacy Builds helper to one explicit source branch.

    The helper's branch selector predates the post-merge exact-main rehearsal and is
    a module constant used by its build metadata checks. The CLI is single-threaded,
    so this bounded adapter can reuse that hardened path without duplicating provider
    logic. The original value is restored even after a provider failure.
    """

    previous = builds._BRANCH
    builds._BRANCH = branch
    try:
        yield
    finally:
        builds._BRANCH = previous


def _sync_runtime_secret(api: builds.CloudflareApi) -> None:
    candidate = builds._staging_dsn_file()
    if candidate.is_symlink():
        raise builds.BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_PATH_INVALID")
    if candidate.exists():
        builds._put_runtime_secret(api)
        return
    if _runtime_secret_present(api):
        print("CLOUDFLARE_STAGING_DATABASE_SECRET=REUSED")
        return
    raise builds.BootstrapStopped("CLOUDFLARE_STAGING_DATABASE_SECRET_MISSING")


def _create_gated_trigger(
    api: builds.CloudflareApi,
    *,
    worker_tag: str,
    connection_uuid: str,
    build_token_uuid: str,
) -> str:
    rows = builds._list(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/builds/workers/{worker_tag}/triggers",
        ),
        "CLOUDFLARE_TRIGGERS_INVALID",
    )
    if rows:
        for row in rows:
            builds._object(row, "CLOUDFLARE_TRIGGER_INVALID")
        raise builds.BootstrapStopped("CLOUDFLARE_GATED_TRIGGER_PREEXISTED")

    desired = builds._desired_trigger(connection_uuid, build_token_uuid)
    desired["branch_includes"] = [_GATED_AUTOBUILD_SENTINEL_BRANCH]
    result = builds._object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/triggers",
            body={**desired, "external_script_id": worker_tag},
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_TRIGGER_CREATE_INVALID",
    )
    trigger_uuid = builds._provider_uuid(
        result.get("trigger_uuid"),
        "CLOUDFLARE_TRIGGER_UUID_INVALID",
    )
    builds._validate_trigger_configuration(
        result,
        trigger_uuid,
        worker_tag,
        connection_uuid,
        desired,
    )
    print("CLOUDFLARE_GATED_TRIGGER=CREATED")
    return trigger_uuid


def _start_exact_manual_build(
    api: builds.CloudflareApi,
    *,
    trigger_uuid: str,
    expected_sha: str,
) -> str:
    result = builds._object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/triggers/{trigger_uuid}/builds",
            body={"branch": builds._BRANCH, "commit_hash": expected_sha},
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_BUILD_CREATE_INVALID",
    )
    build_uuid = builds._provider_uuid(
        result.get("build_uuid"),
        "CLOUDFLARE_BUILD_UUID_INVALID",
    )
    print("CLOUDFLARE_BUILD_SOURCE=GATED_MANUAL_EXACT_SHA")
    return build_uuid


def _prepare_candidate(api: builds.CloudflareApi, sha: str) -> tuple[str, str]:
    api.request("GET", f"/accounts/{api.account_id}/builds/account/limits")
    print("CLOUDFLARE_BUILDS_API=READY")
    token_id = builds._verify_token(api)
    connection_uuid = builds._ensure_repo_connection(api)
    build_token_uuid = builds._ensure_build_token(api, token_id)
    worker_tag = builds._staging_worker_tag(api)
    _sync_runtime_secret(api)
    trigger_uuid = _create_gated_trigger(
        api,
        worker_tag=worker_tag,
        connection_uuid=connection_uuid,
        build_token_uuid=build_token_uuid,
    )
    build_uuid = _start_exact_manual_build(
        api,
        trigger_uuid=trigger_uuid,
        expected_sha=sha,
    )
    print("CLOUDFLARE_GATED_TRIGGER=ARMED_UNTIL_BUILD_TERMINAL")
    return worker_tag, build_uuid


def run(expected_sha: str, *, source_branch: str = builds._BRANCH) -> str:
    sha = _assert_exact_head(expected_sha)
    branch = _source_branch(source_branch)
    token = builds._required_env("CLOUDFLARE_API_TOKEN")
    account_id = builds._required_env("CLOUDFLARE_ACCOUNT_ID")
    api = builds.CloudflareApi(account_id, token)

    primary: builds.BootstrapStopped | None = None
    build_uuid: str | None = None
    url: str | None = None
    with _candidate_source_branch(branch):
        try:
            _, build_uuid = _prepare_candidate(api, sha)
            builds._wait_build(api, build_uuid, sha)
            url = builds._staging_url(api)
            sync_bootstrap_origin_custody(
                api,
                staging_origin=url,
                expected_sha=sha,
            )
        except builds.BootstrapStopped as exc:
            primary = exc

        cleanup: builds.BootstrapStopped | None = None
        try:
            quarantine_staging_autobuild(api, expected_sha=sha, verify_head=False)
        except builds.BootstrapStopped as exc:
            cleanup = exc

    if cleanup is not None:
        if primary is not None:
            print(f"CLOUDFLARE_GATED_CANDIDATE_PRIMARY_FAILURE={primary.code}")
        raise builds.BootstrapStopped(
            "CLOUDFLARE_GATED_CANDIDATE_CLEANUP_FAILED",
            status=cleanup.status,
        ) from None
    if primary is not None:
        raise primary
    if build_uuid is None or url is None:
        raise builds.BootstrapStopped("CLOUDFLARE_GATED_CANDIDATE_RESULT_MISSING")

    builds._write_output("staging_url", url)
    builds._write_output("cloudflare_build_uuid", build_uuid)
    print(f"CLOUDFLARE_CF_C_CANDIDATE=DEPLOYED url={url}")
    return url


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument(
        "--source-branch",
        default=builds._BRANCH,
        choices=tuple(sorted(_ALLOWED_SOURCE_BRANCHES)),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args.expected_sha, source_branch=args.source_branch)
    except builds.BootstrapStopped as exc:
        fields = ["CLOUDFLARE_CF_C_CANDIDATE=STOPPED", f"code={exc.code}"]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
