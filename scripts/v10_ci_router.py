from __future__ import annotations

import argparse
from pathlib import Path
import sys


CATEGORIES = (
    "docs_program",
    "backend_core_contracts",
    "broker_parser_data",
    "frontend",
    "infrastructure_bootstrap",
    "ai_cortex_evals",
    "dependency_toolchain",
    "release_security_authority",
)


def classify_path(path: str) -> set[str]:
    normalized = path.strip().replace("\\", "/").lstrip("./")
    if not normalized:
        return set()
    categories: set[str] = set()

    if normalized.startswith(("docs/", "knowledge/")) or normalized in {
        "AGENTS.md",
        "README.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
    }:
        categories.add("docs_program")

    if (
        normalized.startswith("omni_cio/")
        or (
            normalized.startswith("tests/")
            and not normalized.startswith("tests/toolchain/frontend/")
        )
        or normalized
        in {
            "app.py",
            "app_v371.py",
            "app_v360.py",
            "main.py",
        }
    ):
        categories.add("backend_core_contracts")

    if normalized.startswith(("omni_cio/reconciliation/", "tests/fixtures/broker")):
        categories.add("broker_parser_data")

    if normalized.startswith(("apps/web/", "tests/toolchain/frontend/")):
        categories.add("frontend")

    if normalized.startswith(
        ("infrastructure/", "deploy/", "ops/")
    ) or normalized.startswith("scripts/bootstrap"):
        categories.add("infrastructure_bootstrap")

    if normalized.startswith(("ai/", "tests/contracts/ai/", "tests/evals/")):
        categories.add("ai_cortex_evals")

    if (
        normalized.startswith(("requirements", "constraints"))
        or normalized in {"pyproject.toml", "package.json", "package-lock.json"}
        or "V10_TOOLCHAIN_BASELINE" in normalized
        or normalized == ".github/dependabot.yml"
    ):
        categories.add("dependency_toolchain")

    if (
        normalized.startswith(".github/workflows/")
        or normalized.startswith("scripts/check_")
        or normalized.startswith("scripts/v10_")
        or "V10_RELEASE" in normalized
        or "V10_SECURITY" in normalized
        or "V10_GITHUB_PRO" in normalized
        or normalized in {"SECURITY.md", ".github/CODEOWNERS"}
    ):
        categories.add("release_security_authority")

    if not categories:
        # Unknown paths are deliberately conservative. A new root cannot silently
        # evade clean-room compatibility or release/security review.
        categories.update({"backend_core_contracts", "release_security_authority"})
    return categories


def classify(paths: list[str]) -> dict[str, object]:
    categories: set[str] = set()
    for path in paths:
        categories.update(classify_path(path))

    docs_only = bool(categories) and categories == {"docs_program"}
    fast_frontend = bool(
        categories.intersection(
            {"frontend", "dependency_toolchain", "release_security_authority"}
        )
    )
    windows_python = bool(
        categories.intersection(
            {
                "backend_core_contracts",
                "broker_parser_data",
                "infrastructure_bootstrap",
                "dependency_toolchain",
                "release_security_authority",
            }
        )
    )
    windows_frontend = bool(
        categories.intersection(
            {"frontend", "dependency_toolchain", "release_security_authority"}
        )
    )

    return {
        "categories": sorted(categories),
        "docs_only": docs_only,
        "fast_frontend": fast_frontend,
        "hosted_windows_python": windows_python,
        "hosted_windows_frontend": windows_frontend,
        "release_matrix": "release_security_authority" in categories,
    }


def _bool(value: object) -> str:
    return "true" if value is True else "false"


def emit_github_outputs(result: dict[str, object], path: Path) -> None:
    lines = [
        f"docs_only={_bool(result['docs_only'])}",
        f"fast_frontend={_bool(result['fast_frontend'])}",
        f"hosted_windows_python={_bool(result['hosted_windows_python'])}",
        f"hosted_windows_frontend={_bool(result['hosted_windows_frontend'])}",
        f"release_matrix={_bool(result['release_matrix'])}",
        "categories=" + ",".join(str(item) for item in result["categories"]),
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify V10 changed paths for hosted CI"
    )
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--paths-file")
    parser.add_argument("--github-output")
    args = parser.parse_args(argv)

    paths = list(args.paths)
    if args.paths_file:
        paths.extend(
            line.strip()
            for line in Path(args.paths_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    if not paths:
        print("No changed paths supplied; failing closed.", file=sys.stderr)
        return 2

    result = classify(paths)
    print("V10 CI route categories:", ",".join(result["categories"]))
    print(
        "hosted_windows_python=",
        _bool(result["hosted_windows_python"]),
        "hosted_windows_frontend=",
        _bool(result["hosted_windows_frontend"]),
    )
    if args.github_output:
        emit_github_outputs(result, Path(args.github_output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
