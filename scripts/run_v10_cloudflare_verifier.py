from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
_SHA = re.compile(r"^[0-9a-f]{40}$")
_WEB_ROOT = "apps/web"


def _governance() -> None:
    subprocess.run(
        [sys.executable, "scripts/check_v10_cloudflare_platform_authority.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_v10_cloudflare_public_product_integrated.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_v10_cloudflare_builds_verifier.py"],
        cwd=ROOT,
        check=True,
    )


def _web_static() -> None:
    subprocess.run(
        ["npm", "ci", "--ignore-scripts", "--prefix", _WEB_ROOT],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["npm", "run", "--prefix", _WEB_ROOT, "typecheck"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["npm", "run", "--prefix", _WEB_ROOT, "lint"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["npm", "run", "--prefix", _WEB_ROOT, "test"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["npm", "run", "--prefix", _WEB_ROOT, "build"],
        cwd=ROOT,
        check=True,
    )


def _python_static() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "apps",
            "omni_cio",
            "scripts",
        ],
        cwd=ROOT,
        check=True,
    )


def _security_contracts() -> None:
    subprocess.run(
        [sys.executable, "scripts/check_ci_security_baseline.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_v10_repository_boundaries.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_v10_wp17_web_security.py"],
        cwd=ROOT,
        check=True,
    )


def _runtime_contracts() -> None:
    subprocess.run(
        [sys.executable, "scripts/check_v10_toolchain_baseline.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_v10_public_product_plan.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_v10_ci_cost_control.py"],
        cwd=ROOT,
        check=True,
    )


def _release_provenance() -> None:
    subprocess.run(
        [sys.executable, "scripts/check_v10_regression_shield.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_v10_release_provenance",
        ],
        cwd=ROOT,
        check=True,
    )


@dataclass(frozen=True, slots=True)
class Shard:
    identifier: str
    runner: Callable[[], None]


SHARDS: tuple[Shard, ...] = (
    Shard("CFV-1-GOVERNANCE", _governance),
    Shard("CFV-2-WEB-STATIC", _web_static),
    Shard("CFV-3-PYTHON-STATIC", _python_static),
    Shard("CFV-4-SECURITY-CONTRACTS", _security_contracts),
    Shard("CFV-5-RUNTIME-CONTRACTS", _runtime_contracts),
    Shard("CFV-6-RELEASE-PROVENANCE", _release_provenance),
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


def run(identifier: str, *, env: Mapping[str, str] | None = None) -> int:
    environment = os.environ if env is None else env
    source_sha = _provider_sha(environment)
    shard = _shard(identifier)
    print(f"Cloudflare verifier shard: {shard.identifier}")
    print(f"Exact source SHA: {source_sha or 'LOCAL_UNBOUND'}")
    try:
        shard.runner()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"CLOUDFLARE_VERIFIER_COMMAND_FAILED:{exc.returncode}:{shard.identifier}"
        ) from None
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
