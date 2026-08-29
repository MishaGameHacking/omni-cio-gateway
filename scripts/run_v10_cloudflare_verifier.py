from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class Shard:
    identifier: str
    commands: tuple[tuple[str, ...], ...]


SHARDS: tuple[Shard, ...] = (
    Shard(
        "CFV-1-GOVERNANCE",
        (
            (sys.executable, "scripts/check_v10_cloudflare_platform_authority.py"),
            (sys.executable, "scripts/check_v10_cloudflare_public_product_integrated.py"),
            (sys.executable, "scripts/check_v10_cloudflare_builds_verifier.py"),
        ),
    ),
    Shard(
        "CFV-2-WEB-STATIC",
        (
            ("npm", "ci", "--prefix", "apps/web"),
            ("npm", "run", "--prefix", "apps/web", "typecheck"),
            ("npm", "run", "--prefix", "apps/web", "lint"),
            ("npm", "run", "--prefix", "apps/web", "test"),
            ("npm", "run", "--prefix", "apps/web", "build"),
        ),
    ),
    Shard(
        "CFV-3-PYTHON-STATIC",
        (
            (
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "apps",
                "omni_cio",
                "scripts",
            ),
        ),
    ),
    Shard(
        "CFV-4-SECURITY-CONTRACTS",
        (
            (sys.executable, "scripts/check_ci_security_baseline.py"),
            (sys.executable, "scripts/check_v10_repository_boundaries.py"),
            (sys.executable, "scripts/check_v10_wp17_web_security.py"),
        ),
    ),
    Shard(
        "CFV-5-RUNTIME-CONTRACTS",
        (
            (sys.executable, "scripts/check_v10_toolchain_baseline.py"),
            (sys.executable, "scripts/check_v10_public_product_plan.py"),
            (sys.executable, "scripts/check_v10_ci_cost_control.py"),
        ),
    ),
    Shard(
        "CFV-6-RELEASE-PROVENANCE",
        (
            (sys.executable, "scripts/check_v10_regression_shield.py"),
            (
                sys.executable,
                "-m",
                "unittest",
                "tests.test_v10_release_provenance",
            ),
        ),
    ),
)


def _provider_sha(env: Mapping[str, str]) -> str | None:
    workers_ci = env.get("WORKERS_CI", "").strip().lower()
    worker_sha = env.get("WORKERS_CI_COMMIT_SHA", "").strip().lower()
    github_sha = env.get("GITHUB_SHA", "").strip().lower()
    if workers_ci:
        if _SHA.fullmatch(worker_sha) is None:
            raise RuntimeError("CLOUDFLARE_VERIFIER_WORKERS_SHA_REQUIRED")
        if github_sha and github_sha != worker_sha:
            raise RuntimeError("CLOUDFLARE_VERIFIER_SHA_MISMATCH")
        return worker_sha
    if github_sha:
        if _SHA.fullmatch(github_sha) is None:
            raise RuntimeError("CLOUDFLARE_VERIFIER_GITHUB_SHA_INVALID")
        return github_sha
    return None


def _shard(identifier: str) -> Shard:
    for candidate in SHARDS:
        if candidate.identifier == identifier:
            return candidate
    raise RuntimeError("CLOUDFLARE_VERIFIER_SHARD_UNKNOWN")


def _run(command: Sequence[str]) -> None:
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"CLOUDFLARE_VERIFIER_COMMAND_FAILED:{completed.returncode}:"
            f"{' '.join(command)}"
        )


def run(identifier: str, *, env: Mapping[str, str] | None = None) -> int:
    environment = os.environ if env is None else env
    source_sha = _provider_sha(environment)
    shard = _shard(identifier)
    print(f"Cloudflare verifier shard: {shard.identifier}")
    print(f"Exact source SHA: {source_sha or 'LOCAL_UNBOUND'}")
    for command in shard.commands:
        _run(command)
    print(f"Cloudflare verifier shard PASS: {shard.identifier}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = tuple(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            "usage: python scripts/run_v10_cloudflare_verifier.py <SHARD_ID>",
            file=sys.stderr,
        )
        return 2
    try:
        return run(args[0])
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
