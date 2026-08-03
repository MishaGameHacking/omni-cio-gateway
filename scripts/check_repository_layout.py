from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "app.py",
    "render.yaml",
    "requirements.in",
    "requirements.txt",
    "requirements-dev.in",
    "requirements-dev.txt",
    "pyproject.toml",
    ".env.example",
    "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    "docs/master-plan/README.md",
    "docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf",
    "docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt",
    "docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md",
    "docs/architecture/V9_BASELINE_FREEZE_AND_MIGRATION.md",
    "docs/architecture/REAL_TRADING_V1.md",
    "docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md",
    "docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md",
    "gpt/README.md",
    "gpt/SETUP_INDEX.md",
    "gpt/CONFIGURATION.md",
    "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt",
    "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt",
    "gpt/ACTIONS_CATALOG.md",
    "gpt/SECRETS_AND_RENDER.md",
    "gpt/BOT_ONLY_FILE_MANIFEST.md",
    "gpt/NEW_CHAT_PROMPT.md",
    "gpt/PROJECT_INSTRUCTIONS.md",
    "scripts/check_ci_security_baseline.py",
    "scripts/check_gpt_configuration_consistency.py",
    "tests/test_ci_security_baseline.py",
    "tests/test_gpt_configuration_consistency.py",
    "omni_cio/sandbox/client_v1.py",
    "omni_cio/sandbox/service_v1.py",
    "omni_cio/sandbox/routes_v1.py",
    "omni_cio/real_trading/client_v1.py",
    "omni_cio/real_trading/service_v1.py",
    "omni_cio/real_trading/routes_v1.py",
    "omni_cio/real_trading/durable_journal_factory_v1.py",
    "tests/test_sandbox_trading_v1.py",
    "tests/test_real_trading_core_v1.py",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    ".github/workflows/regression-shield.yml",
)

FORBIDDEN_TRACKED_NAMES = {".env", "pytest-results.xml"}
FORBIDDEN_WORKFLOWS = {"apply-v390.yml", "pr03-bootstrap.yml", "upgrade-v390.yml"}

SANDBOX_ROOT = ROOT / "omni_cio" / "sandbox"
REAL_ROOT = ROOT / "omni_cio" / "real_trading"

SANDBOX_HOST = "https://sandbox-invest-public-api.tbank.ru/rest"
REAL_HOST = "https://invest-public-api.tbank.ru/rest"


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def read_tree(root: Path, failures: list[str]) -> str:
    if not root.is_dir():
        fail(f"missing runtime directory: {root.relative_to(ROOT)}", failures)
        return ""
    parts: list[str] = []
    for path in sorted(root.glob("*.py")):
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except OSError as exc:
            fail(f"cannot read {path.relative_to(ROOT)}: {exc}", failures)
    return "\n".join(parts)


def scan_execution_boundaries(failures: list[str]) -> None:
    sandbox = read_tree(SANDBOX_ROOT, failures)
    real = read_tree(REAL_ROOT, failures)

    if SANDBOX_HOST not in sandbox:
        fail("sandbox runtime is not hard-bound to the canonical Sandbox host", failures)
    if "TINVEST_SANDBOX_TOKEN" not in sandbox:
        fail("sandbox runtime does not require TINVEST_SANDBOX_TOKEN", failures)
    if "SANDBOX_TRADING_ENABLED" not in sandbox:
        fail("sandbox runtime does not expose a kill switch", failures)
    if REAL_HOST in sandbox or "TINVEST_TRADING_TOKEN" in sandbox:
        fail("sandbox runtime crosses the real execution credential/host boundary", failures)

    if REAL_HOST not in real:
        fail("real runtime is not hard-bound to the canonical production REST host", failures)
    if "TINVEST_TRADING_TOKEN" not in real:
        fail("real runtime does not require the dedicated trading token", failures)
    if "REAL_TRADING_ENABLED" not in real:
        fail("real runtime does not expose the master kill switch", failures)
    if "PostOrder" not in real or "GetOrderState" not in real:
        fail("real runtime is missing submit/reconciliation contract markers", failures)
    if "confirmMarginTrade" not in real or "False" not in real:
        fail("real runtime does not visibly hard-disable margin confirmation", failures)
    if 'os.environ.get("TINVEST_TOKEN"' in real or "TINVEST_SANDBOX_TOKEN" in real:
        fail("real runtime references a forbidden fallback broker credential", failures)

    # Broker mutation strings must stay isolated to the dedicated execution contours.
    protected_roots = {"omni_cio/real_trading", "omni_cio/sandbox"}
    mutation_markers = (
        "OrdersService/PostOrder",
        "PostOrderAsync",
        "ReplaceOrder",
        "Withdraw",
        "TransferSecurities",
    )
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("tests/") or relative.startswith("scripts/"):
            continue
        if any(relative.startswith(prefix + "/") for prefix in protected_roots):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            fail(f"cannot inspect runtime source {relative}: {exc}", failures)
            continue
        for marker in mutation_markers:
            if marker in source:
                fail(
                    f"broker mutation marker outside isolated execution contour: {relative} ({marker})",
                    failures,
                )


def scan_program_and_recovery(failures: list[str]) -> None:
    program = ROOT / "docs" / "master-plan" / "OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md"
    if program.is_file():
        text = program.read_text(encoding="utf-8")
        if "OWNER-APPROVED / PROGRAM LOCKED" not in text:
            fail("v9 program is not marked owner-approved/program-locked", failures)

    setup = ROOT / "gpt" / "SETUP_INDEX.md"
    if setup.is_file():
        text = setup.read_text(encoding="utf-8")
        if "CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt" not in text:
            fail("GPT recovery does not point to v8.6.1 Compact", failures)
        if "OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md" not in text:
            fail("GPT recovery does not point to the active v9 program", failures)
        if "ONLY remaining release gate" in text:
            fail("GPT recovery still claims the completed Phase 4 is pending", failures)


def main() -> int:
    failures: list[str] = []

    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).is_file():
            fail(f"missing required file: {relative}", failures)

    render_path = ROOT / "render.yaml"
    if render_path.is_file():
        render_text = render_path.read_text(encoding="utf-8")
        if "uvicorn app:app --host 0.0.0.0 --port $PORT" not in render_text:
            fail("render.yaml does not preserve app:app entrypoint", failures)

    app_path = ROOT / "app.py"
    if app_path.is_file():
        app_text = app_path.read_text(encoding="utf-8")
        if 'ENTRYPOINT = "app:app"' not in app_text:
            fail("app.py does not declare ENTRYPOINT = app:app", failures)
        if "trading_methods" not in app_text:
            fail("app.py does not expose trading_methods health marker", failures)

    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.name in FORBIDDEN_TRACKED_NAMES:
            fail(f"forbidden generated/secret file: {path.relative_to(ROOT)}", failures)
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            fail(f"generated Python artifact: {path.relative_to(ROOT)}", failures)

    workflow_dir = ROOT / ".github" / "workflows"
    for name in FORBIDDEN_WORKFLOWS:
        if (workflow_dir / name).exists():
            fail(f"obsolete one-time workflow still present: {name}", failures)

    scan_execution_boundaries(failures)
    scan_program_and_recovery(failures)

    if failures:
        print("Repository layout check failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("Repository layout check passed.")
    print(f"Required files checked: {len(REQUIRED_PATHS)}")
    print("Product surface: single Omni-CIO Custom GPT + Gateway")
    print("Protected baseline: v8.6.1 read-only + Sandbox + confirmed real execution")
    print("Active development program: Omni-CIO v9 Portfolio Autopilot")
    print("Gateway entrypoint: app:app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
