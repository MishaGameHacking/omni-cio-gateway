from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = "docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(
            f"TIMEWEB_RUNTIME_REACHABILITY_SOURCE_UNREADABLE:{path}"
        ) from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_JSON_ROOT_INVALID")
    return value


def _string_tuple(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"TIMEWEB_RUNTIME_REACHABILITY_CONTRACT_INVALID:{key}")
    if not all(isinstance(item, str) and item for item in value):
        raise RuntimeError(f"TIMEWEB_RUNTIME_REACHABILITY_CONTRACT_INVALID:{key}")
    rows = tuple(value)
    if len(rows) != len(set(rows)):
        raise RuntimeError(f"TIMEWEB_RUNTIME_REACHABILITY_CONTRACT_DUPLICATE:{key}")
    return rows


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_map(root: Path, scan_roots: tuple[str, ...]) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for relative in scan_roots:
        directory = root / relative
        if not directory.is_dir() or directory.is_symlink():
            raise RuntimeError(
                f"TIMEWEB_RUNTIME_REACHABILITY_SCAN_ROOT_MISSING:{relative}"
            )
        for path in directory.rglob("*.py"):
            if path.is_symlink():
                raise RuntimeError(
                    f"TIMEWEB_RUNTIME_REACHABILITY_SYMLINK_FORBIDDEN:{path}"
                )
            module = _module_name(root, path)
            if module:
                modules[module] = path
    return modules


def _relative_base(current: str, level: int) -> list[str]:
    package = current.split(".")[:-1]
    hops = max(level - 1, 0)
    if hops > len(package):
        return []
    return package[: len(package) - hops]


def _from_import_targets(
    current: str,
    node: ast.ImportFrom,
    modules: dict[str, Path],
) -> set[str]:
    if node.level:
        base_parts = _relative_base(current, node.level)
        if node.module:
            base_parts.extend(node.module.split("."))
        base = ".".join(base_parts)
    else:
        base = node.module or ""

    targets = {base} if base in modules else set()
    for alias in node.names:
        if alias.name == "*":
            continue
        candidate = f"{base}.{alias.name}" if base else alias.name
        if candidate in modules:
            targets.add(candidate)
    return targets


def _import_targets(
    current: str,
    tree: ast.AST,
    modules: dict[str, Path],
) -> set[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(
                alias.name for alias in node.names if alias.name in modules
            )
        elif isinstance(node, ast.ImportFrom):
            targets.update(_from_import_targets(current, node, modules))
    return targets


def _reachable(entry: str, modules: dict[str, Path]) -> frozenset[str]:
    if entry not in modules:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_ENTRY_MISSING")
    pending = [entry]
    visited: set[str] = set()
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        path = modules[module]
        try:
            tree = ast.parse(_read(path), filename=path.as_posix())
        except SyntaxError as exc:
            raise RuntimeError(
                f"TIMEWEB_RUNTIME_REACHABILITY_SYNTAX_INVALID:{module}"
            ) from exc
        pending.extend(
            target
            for target in sorted(_import_targets(module, tree, modules))
            if target not in visited
        )
    return frozenset(visited)


def _retired_modules(
    root: Path,
    inventory: dict[str, Any],
    classifications: frozenset[str],
) -> frozenset[str]:
    explicit = inventory.get("explicit_paths")
    if not isinstance(explicit, dict):
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_INVENTORY_INVALID")
    retired: set[str] = set()
    for relative, row in explicit.items():
        if not isinstance(relative, str) or not relative.endswith(".py"):
            continue
        if not isinstance(row, dict) or row.get("classification") not in classifications:
            continue
        path = root / relative
        if path.is_file():
            retired.add(_module_name(root, path))
    return frozenset(retired)


def _config(
    root: Path,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], str]:
    contract = _json(root / _CONTRACT)
    config = contract.get("runtime_reachability")
    if not isinstance(config, dict):
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_CONTRACT_MISSING")
    entry = config.get("production_entry_module")
    inventory_path = config.get("inventory_path")
    if not isinstance(entry, str) or not entry:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_ENTRY_INVALID")
    if not isinstance(inventory_path, str) or not inventory_path:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_INVENTORY_PATH_INVALID")
    return (
        entry,
        _string_tuple(config, "required_reachable_modules"),
        _string_tuple(config, "scan_roots"),
        _string_tuple(config, "retired_classifications"),
        _string_tuple(config, "forbidden_module_fragments"),
        inventory_path,
    )


def _validate_required(
    reachable: frozenset[str],
    required: tuple[str, ...],
) -> None:
    missing = sorted(set(required) - set(reachable))
    if missing:
        raise RuntimeError(
            "TIMEWEB_RUNTIME_REACHABILITY_TELEGRAM_PATH_MISSING:" + ",".join(missing)
        )


def _validate_retired(
    reachable: frozenset[str],
    retired: frozenset[str],
) -> None:
    reached = sorted(set(reachable) & set(retired))
    if reached:
        raise RuntimeError(
            "TIMEWEB_RUNTIME_REACHABILITY_RETIRED_MODULE_REACHED:" + ",".join(reached)
        )


def _validate_fragments(
    reachable: frozenset[str],
    fragments: tuple[str, ...],
) -> None:
    folded = tuple(item.casefold() for item in fragments)
    hits = sorted(
        module
        for module in reachable
        if any(fragment in module.casefold() for fragment in folded)
    )
    if hits:
        raise RuntimeError(
            "TIMEWEB_RUNTIME_REACHABILITY_RETIRED_FRAGMENT_REACHED:" + ",".join(hits)
        )


def validate(root: Path = ROOT) -> frozenset[str]:
    entry, required, scan_roots, classes, fragments, inventory_path = _config(root)
    modules = _module_map(root, scan_roots)
    reachable = _reachable(entry, modules)
    _validate_required(reachable, required)
    retired = _retired_modules(
        root,
        _json(root / inventory_path),
        frozenset(classes),
    )
    _validate_retired(reachable, retired)
    _validate_fragments(reachable, fragments)
    return reachable


def main() -> int:
    try:
        reachable = validate()
    except RuntimeError as exc:
        print(f"V10_TIMEWEB_RUNTIME_REACHABILITY=FAIL code={exc}", file=sys.stderr)
        return 1
    print(
        "V10_TIMEWEB_RUNTIME_REACHABILITY=PASS "
        f"reachable_modules={len(reachable)} retired_reachable=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
