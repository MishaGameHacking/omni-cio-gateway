from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Callable


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


def _is_docs_path(path: str) -> bool:
    return path.startswith(("docs/", "knowledge/")) or path in {
        "AGENTS.md",
        "README.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
    }


def _is_backend_path(path: str) -> bool:
    if path.startswith("omni_cio/"):
        return True
    if path.startswith("tests/"):
        return not path.startswith("tests/toolchain/frontend/")
    return path in {"app.py", "app_v371.py", "app_v360.py", "main.py"}


def _is_broker_parser_path(path: str) -> bool:
    return path.startswith(("omni_cio/reconciliation/", "tests/fixtures/broker"))


def _is_frontend_path(path: str) -> bool:
    return path.startswith(("apps/web/", "tests/toolchain/frontend/"))


def _is_infrastructure_path(path: str) -> bool:
    return path.startswith(("infrastructure/", "deploy/", "ops/", "scripts/bootstrap"))


def _is_ai_cortex_path(path: str) -> bool:
    return path.startswith(("ai/", "tests/contracts/ai/", "tests/evals/"))


def _is_dependency_path(path: str) -> bool:
    return (
        path.startswith(("requirements", "constraints"))
        or path
        in {
            "pyproject.toml",
            "package.json",
            "package-lock.json",
            ".github/dependabot.yml",
        }
        or "V10_TOOLCHAIN_BASELINE" in path
    )


def _is_release_security_path(path: str) -> bool:
    return (
        path.startswith((".github/workflows/", "scripts/check_", "scripts/v10_"))
        or "V10_RELEASE" in path
        or "V10_SECURITY" in path
        or "V10_GITHUB_PRO" in path
        or path in {"SECURITY.md", ".github/CODEOWNERS"}
    )


_PATH_CLASSIFIERS: tuple[tuple[str, Callable[[str], bool]], ...] = (
    ("docs_program", _is_docs_path),
    ("backend_core_contracts", _is_backend_path),
    ("broker_parser_data", _is_broker_parser_path),
    ("frontend", _is_frontend_path),
    ("infrastructure_bootstrap", _is_infrastructure_path),
    ("ai_cortex_evals", _is_ai_cortex_path),
    ("dependency_toolchain", _is_dependency_path),
    ("release_security_authority", _is_release_security_path),
)


def classify_path(path: str) -> set[str]:
    normalized = path.strip().replace("\\", "/").lstrip("./")
    if not normalized:
        return set()

    categories = {
        category for category, classifier in _PATH_CLASSIFIERS if classifier(normalized)
    }
    if categories:
        return categories

    # Unknown paths are deliberately conservative. A new root cannot silently
    # evade clean-room compatibility or release/security review.
    return {"backend_core_contracts", "release_security_authority"}


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
