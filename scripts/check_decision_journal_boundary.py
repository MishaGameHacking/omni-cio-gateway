from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "omni_cio" / "decision_journal"
CONTRACT_PATH = ROOT / "omni_cio" / "contracts" / "v1" / "decision_journal.py"

REQUIRED_PATHS = (
    "omni_cio/contracts/v1/decision_journal.py",
    "omni_cio/decision_journal/__init__.py",
    "omni_cio/decision_journal/evaluation_v1.py",
    "omni_cio/decision_journal/journal_v1.py",
    "omni_cio/decision_journal/replay_v1.py",
    "omni_cio/decision_journal/upstash_journal_v1.py",
    "tests/test_decision_journal_v1.py",
    "tests/test_decision_journal_upstash_v1.py",
    "tests/test_decision_journal_boundary_v1.py",
    "docs/architecture/V9_DECISION_JOURNAL_EVALUATION.md",
    "docs/architecture/V9_DECISION_JOURNAL_THREAT_MODEL.md",
    "docs/architecture/V9_DECISION_JOURNAL_DATA_CONTRACT.md",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "omni_cio.real_trading",
    "omni_cio.sandbox",
    "t_tech.invest",
    "t_tech_investments",
)

FORBIDDEN_CALL_ATTRIBUTES = {
    "execute_trade",
    "post_order",
    "post_order_async",
    "replace_order",
    "cancel_order",
    "post_stop_order",
    "withdraw",
    "transfer",
}

FORBIDDEN_RUNTIME_TEXT = (
    "TINVEST_TRADING_TOKEN",
    "TINVEST_SANDBOX_TOKEN",
    "RealTradingServiceV1",
    "RealTradingRestClientV1",
    "SandboxTradingServiceV1",
    "PostOrder",
    "PostOrderAsync",
    "ReplaceOrder",
    "CancelOrder",
    "ORDER_TYPE_MARKET",
    "ORDER_TYPE_BESTPRICE",
    "confirmMarginTrade=True",
    "allow_autonomous_real_execution=True",
)

REQUIRED_SAFETY_LITERALS = (
    "expectations_rewritable: Literal[False] = False",
    "counterfactual_fabricated: Literal[False] = False",
    "production_rules_modified: Literal[False] = False",
    "self_modification_authorized: Literal[False] = False",
    "full_account_identifier_present: Literal[False] = False",
    "raw_private_payload_present: Literal[False] = False",
    "production_change_applied: Literal[False] = False",
)


def _fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def _scan(path: Path, failures: list[str]) -> None:
    relative = path.relative_to(ROOT)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(relative))
    except (OSError, SyntaxError) as exc:
        _fail(f"cannot inspect {relative}: {exc}", failures)
        return

    for forbidden in FORBIDDEN_RUNTIME_TEXT:
        if forbidden in source:
            _fail(
                f"Decision Journal crosses protected authority boundary: {relative}: {forbidden}",
                failures,
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    _fail(
                        f"Decision Journal imports forbidden execution package: {relative}: {item.name}",
                        failures,
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                _fail(
                    f"Decision Journal imports forbidden execution package: {relative}: {module}",
                    failures,
                )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_CALL_ATTRIBUTES:
                _fail(
                    f"Decision Journal calls forbidden mutation method: {relative}:{node.lineno} ({node.func.attr})",
                    failures,
                )


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).is_file():
            _fail(f"missing WP14 required path: {relative}", failures)

    if not RUNTIME_ROOT.is_dir():
        _fail("WP14 Decision Journal runtime directory is missing", failures)
    else:
        for path in sorted(RUNTIME_ROOT.glob("*.py")):
            _scan(path, failures)

    if CONTRACT_PATH.is_file():
        _scan(CONTRACT_PATH, failures)
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        for literal in REQUIRED_SAFETY_LITERALS:
            if literal not in contract:
                _fail(f"WP14 safety literal missing: {literal}", failures)

    if failures:
        print("Decision Journal boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Decision Journal boundary check passed.")
    print("Storage model: append-only immutable decisions + separate outcomes/evaluations")
    print("Counterfactuals: evidence-bound only; unavailable remains unavailable")
    print("Offline replay: sanitized/synthetic/fake-broker only")
    print("Production self-modification: disabled")
    print("Broker/Sandbox mutation authority: absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
