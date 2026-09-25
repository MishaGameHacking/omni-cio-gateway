from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"TIMEWEB_RUNTIME_REACHABILITY_SOURCE_UNREADABLE:{path}") from exc

def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_JSON_ROOT_INVALID")
    return value

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
        if not directory.is_dir():
            raise RuntimeError(f"TIMEWEB_RUNTIME_REACHABILITY_SCAN_ROOT_MISSING:{relative}")
        for path in directory.rglob("*.py"):
            if path.is_symlink():
                raise RuntimeError(f"TIMEWEB_RUNTIME_REACHABILITY_SYMLINK_FORBIDDEN:{path}")
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

def _import_targets(current: str, tree: ast.AST, modules: dict[str, Path]) -> set[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in modules:
                    targets.add(alias.name)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            base_parts = _relative_base(current, node.level)
            if node.module:
                base_parts.extend(node.module.split("."))
            base = ".".join(base_parts)
        else:
            base = node.module or ""
        if base in modules:
            targets.add(base)
        for alias in node.names:
            if alias.name == "*":
                continue
            candidate = f"{base}.{alias.name}" if base else alias.name
            if candidate in modules:
                targets.add(candidate)
    return targets

def _reachable(root: Path, entry: str, modules: dict[str, Path]) -> frozenset[str]:
    if entry not in modules:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_ENTRY_MISSING")
    pending=[entry]
    visited:set[str]=set()
    while pending:
        module=pending.pop()
        if module in visited:
            continue
        visited.add(module)
        path=modules[module]
        try:
            tree=ast.parse(_read(path), filename=path.as_posix())
        except SyntaxError as exc:
            raise RuntimeError(f"TIMEWEB_RUNTIME_REACHABILITY_SYNTAX_INVALID:{module}") from exc
        for target in sorted(_import_targets(module, tree, modules)):
            if target not in visited:
                pending.append(target)
    return frozenset(visited)

def _retired_modules(root: Path, inventory: dict[str, Any], classes: frozenset[str]) -> frozenset[str]:
    explicit=inventory.get("explicit_paths")
    if not isinstance(explicit, dict):
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_INVENTORY_INVALID")
    result:set[str]=set()
    for relative,row in explicit.items():
        if not isinstance(relative,str) or not relative.endswith(".py"):
            continue
        if not isinstance(row,dict) or row.get("classification") not in classes:
            continue
        path=root/relative
        if path.is_file():
            result.add(_module_name(root,path))
    return frozenset(result)

def validate(root: Path = ROOT) -> frozenset[str]:
    contract=_json(root/"docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json")
    config=contract.get("runtime_reachability")
    if not isinstance(config,dict):
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_CONTRACT_MISSING")
    entry=config.get("production_entry_module")
    required=config.get("required_reachable_modules")
    scan_roots=config.get("scan_roots")
    classes=config.get("retired_classifications")
    fragments=config.get("forbidden_module_fragments")
    inventory_path=config.get("inventory_path")
    if not isinstance(entry,str) or not isinstance(inventory_path,str):
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_CONTRACT_INVALID")
    for value in (required,scan_roots,classes,fragments):
        if not isinstance(value,list) or not all(isinstance(item,str) for item in value):
            raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_CONTRACT_INVALID")
    modules=_module_map(root,tuple(scan_roots))
    reachable=_reachable(root,entry,modules)
    missing=sorted(set(required)-set(reachable))
    if missing:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_TELEGRAM_PATH_MISSING:"+",".join(missing))
    inventory=_json(root/inventory_path)
    retired=_retired_modules(root,inventory,frozenset(classes))
    bad=sorted(set(reachable)&set(retired))
    if bad:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_RETIRED_MODULE_REACHED:"+",".join(bad))
    folded=tuple(item.casefold() for item in fragments)
    bad_fragments=sorted(module for module in reachable if any(item in module.casefold() for item in folded))
    if bad_fragments:
        raise RuntimeError("TIMEWEB_RUNTIME_REACHABILITY_RETIRED_FRAGMENT_REACHED:"+",".join(bad_fragments))
    return reachable

def main() -> int:
    try:
        reachable=validate()
    except RuntimeError as exc:
        print(f"V10_TIMEWEB_RUNTIME_REACHABILITY=FAIL code={exc}",file=sys.stderr)
        return 1
    print(f"V10_TIMEWEB_RUNTIME_REACHABILITY=PASS reachable_modules={len(reachable)} retired_reachable=0")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
