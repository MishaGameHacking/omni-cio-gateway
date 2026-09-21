from __future__ import annotations

from pathlib import Path

import scripts.check_v10_cloudflare_candidate_delivery as candidate_guard


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
LEDGER = ROOT / "docs/updates/CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_EXECUTION_LEDGER.md"


def test_cloudflare_system_update_is_accepted_complete() -> None:
    status = STATUS.read_text(encoding="utf-8")

    for marker in (
        "Cloudflare Public Product System Update — **HISTORICAL ACCEPTED COMPLETE / ARCHIVE-IN-PLACE**",
        "V10 Cloudflare Production Release #78",
        "Regression Shield #1617",
        "V10 Engineering Governance #1607",
        "Current authorized functional implementation package: **NONE**",
    ):
        assert marker in status


def test_timeweb_consolidation_supersedes_visual_as_current_package() -> None:
    status = STATUS.read_text(encoding="utf-8")

    assert (
        "## Current next package — TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED"
        in status
    )
    assert "Amendment 18 — Timeweb-only platform consolidation" in status
    assert "WEB-VISUAL remains paused" in status
    assert "WP23+ remains locked" in status


def test_candidate_guard_accepts_historical_closeout_ledger() -> None:
    candidate_guard._validate_ledger()


def test_cloudflare_execution_ledger_is_historical_closeout() -> None:
    ledger = LEDGER.read_text(encoding="utf-8")

    for marker in (
        "ACCEPTED COMPLETE / HISTORICAL EXECUTION RECORD",
        "`RED_REPAIR_ONLY` describes superseded repair checkpoints",
        "CF-D / `CLOUDFLARE-PUBLIC-CUTOVER` | DONE / ACCEPTED",
        "Production Release #78",
        "Update state: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED = ACCEPTED_COMPLETE`",
        "Current next prepared package: `WEB-VISUAL-INTEGRATED` / OWNER START REQUIRED",
    ):
        assert marker in ledger


def test_closeout_keeps_runtime_and_money_locks_fail_closed() -> None:
    status = STATUS.read_text(encoding="utf-8")

    for marker in (
        "`PUBLIC_MULTI_USER_ENABLED=false`",
        "broker write OFF",
        "`trading_methods=false`",
        "`REAL_TRADING_ENABLED=false`",
        "no transfer/withdrawal/margin/leverage/uncovered-short authority",
    ):
        assert marker in status
