from __future__ import annotations

import argparse
import sys

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.manage_v10_cloudflare_production as production
import scripts.run_v10_cloudflare_gated_candidate as gated
from scripts import provision_v10_cloudflare_neon_runtime as runtime
from scripts import provision_v10_render_neon_preview as neon_base
from scripts.bootstrap_v10_cloudflare_production_database_via_staging import (
    BootstrapStopped as LegacyBootstrapStopped,
)
from scripts.cloudflare_staging_secrets import put_staging_runtime_secret
def _cloudflare_api() -> builds.CloudflareApi:
    token = builds._required_env("CLOUDFLARE_API_TOKEN")
    account_id = builds._required_env("CLOUDFLARE_ACCOUNT_ID")
    builds._mask(token)
    return builds.CloudflareApi(account_id, token)


def bootstrap_staging(expected_sha: str) -> None:
    runtime.run(expected_sha, "staging")
    put_staging_runtime_secret(_cloudflare_api())
    print("CLOUDFLARE_NEON_HOSTED_STAGING_BOOTSTRAP=READY")


def _resync_production_branch_custody(expected_sha: str) -> None:
    gated.run(expected_sha, source_branch="main")
    print("CLOUDFLARE_NEON_HOSTED_PRODUCTION_BRANCH_CUSTODY=READY")


def bootstrap_production(expected_sha: str) -> None:
    _resync_production_branch_custody(expected_sha)
    runtime.run(expected_sha, "production")
    production.put_runtime_secret()
    print("CLOUDFLARE_NEON_HOSTED_PRODUCTION_BOOTSTRAP=READY")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    staging = subparsers.add_parser("bootstrap-staging")
    staging.add_argument("--expected-sha", required=True)

    production_parser = subparsers.add_parser("bootstrap-production")
    production_parser.add_argument("--expected-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "bootstrap-staging":
            bootstrap_staging(args.expected_sha)
        else:
            bootstrap_production(args.expected_sha)
    except (
        neon_base.ProvisioningStopped,
        builds.BootstrapStopped,
        LegacyBootstrapStopped,
    ) as exc:
        fields = ["CLOUDFLARE_NEON_HOSTED_BOOTSTRAP=STOPPED", f"code={exc.code}"]
        status = getattr(exc, "status", None)
        if status is not None:
            fields.append(f"status={status}")
        print(" ".join(fields), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
