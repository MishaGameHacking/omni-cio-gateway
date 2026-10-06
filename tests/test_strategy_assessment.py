"""Exact, sourced account-constraint tests; no production accounts or predictions."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from omnicio.portfolio import PortfolioAnalysis, SecurityExposure
from omnicio.strategy import POLICY_KEYS, RATING_LEVELS, preset_document, strategy_catalog
from omnicio.strategy_assessment import IssuerEvidence, assess_strategy_account, rating_notch
from omnicio.tbank import TBankInstrumentMetadata, TBankRating

NOW = datetime(2026, 10, 6, 6, 0, tzinfo=UTC)


def position(uid="bond-a", kind="bond", value="10000", sector="finance"):
    return SecurityExposure(
        uid, uid, "Synthetic " + uid, kind, sector, "RU", False, False, value, None
    )


def snapshot(*positions, nav="100000", cash="90000", blocked="10000", status="observed"):
    return PortfolioAnalysis(
        status,
        nav,
        cash,
        blocked,
        str(Decimal(cash) - Decimal(blocked)),
        len(positions),
        len(positions),
        "100",
        (),
        (),
        positions,
        (),
    )


def document(preset="income"):
    data = preset_document(preset)
    data["profile"]["reserve_rub"] = "20000"
    data["profile"]["planned_withdrawal_rub"] = "10000"
    data["policy"]["securities_tax_rate_percent"] = "13"
    return data


def run(data=None, analysis=None, **kwargs):
    return assess_strategy_account(
        data or document(),
        analysis=analysis or snapshot(position()),
        captured_at=NOW,
        now=NOW,
        **kwargs,
    )


def checks(result):
    return {item["key"]: item for item in result["checks"]}


def metadata(uid="bond-a", maturity=None, **kwargs):
    return TBankInstrumentMetadata(
        uid,
        uid,
        uid,
        "RU_SYNTHETIC",
        "bond",
        "finance",
        "RU",
        False,
        maturity_date=maturity or NOW + timedelta(days=365),
        perpetual=False,
        **kwargs,
    )


@pytest.mark.parametrize("preset", [item["id"] for item in strategy_catalog()["presets"]])
def test_all_ten_have_real_allocation_and_every_control_has_explicit_status(preset):
    result = run(document(preset))
    assert len(result["allocation"]) == 4
    assert sum(Decimal(row["target_rub"]) for row in result["allocation"]) == Decimal("100000")
    assert {item["state"] for item in result["checks"]} <= {
        "evaluated",
        "blocked",
        "unknown",
        "inapplicable",
    }
    keys = checks(result)
    assert len(keys) == len(result["checks"])
    assert set(POLICY_KEYS) <= keys.keys()
    assert {
        "reserve_rub",
        "planned_withdrawal_rub",
        "horizon_months",
        "max_drawdown_percent",
        "liquidity_horizon_days",
        "allow_below_investment_grade",
        "excluded",
        "locked",
        "yield_floor",
        "yield_margin_pp",
        "fund_wrapper_cap_percent",
    } <= keys.keys()
    assert {"rating_caps." + rating for rating in RATING_LEVELS} <= keys.keys()
    assert result["execution_enabled"] is False
    assert result["candidate_selection_ready"] is False
    assert result["proposed_trades"] == []
    assert result["probability_of_profit"] is None
    assert result["method_requirements"]


def test_no_double_subtraction_of_blocks_or_cash_target():
    result = run()
    assert result["cash"]["allocation_capacity_rub"] == "50000"
    assert result["cash"]["blocked_rub"] == "10000"
    data = document()
    data["allocation"] = {"shares": 0, "bonds": 40, "funds": 0, "cash": 60}
    result = run(data)
    assert result["cash"]["allocation_capacity_rub"] == "20000"
    assert result["cash"]["executable_budget"] is False


def test_precision_is_not_rounded_by_allocation_math():
    data = document()
    data["profile"]["reserve_rub"] = "0.00000001"
    data["profile"]["planned_withdrawal_rub"] = "0"
    result = run(data, snapshot(nav="0.12345678", cash="0.12345678", blocked="0"))
    assert result["nav_rub"] == "0.12345678"
    assert sum(Decimal(row["target_rub"]) for row in result["allocation"]) == Decimal("0.12345678")
    assert Decimal(result["cash"]["allocation_capacity_rub"]) > 0


@pytest.mark.parametrize("key", ["reserve_rub", "planned_withdrawal_rub"])
def test_unknown_personal_fact_never_becomes_zero(key):
    data = document()
    data["profile"][key] = None
    result = run(data)
    assert result["cash"]["allocation_capacity_rub"] is None
    assert checks(result)[key]["state"] == "unknown"


def test_unknown_cash_or_inconsistent_cash_prevents_budget():
    for analysis in [
        replace(snapshot(position()), rub_cash_unblocked=None),
        replace(snapshot(position()), rub_cash_unblocked="90000"),
    ]:
        result = run(analysis=analysis)
        assert result["cash"]["allocation_capacity_rub"] is None
        assert checks(result)["cash_budget"]["state"] == "unknown"


def test_insufficient_cash_keeps_deficit_separate_from_zero_budget():
    result = run(analysis=snapshot(position(value="95000"), cash="5000", blocked="0"))
    assert result["cash"]["allocation_capacity_rub"] == "0"
    assert result["cash"]["shortfall_rub"] == "25000"


def test_fx_residual_does_not_become_free_rubles_or_complete_allocation():
    result = run(analysis=snapshot(position(), cash="50000", blocked="0"))
    assert checks(result)["allocation"]["state"] == "unknown"
    assert checks(result)["allocation"]["value"]["unclassified_rub"] == "40000"
    assert result["cash"]["unblocked_rub"] == "50000"
    assert not any(row["complete"] for row in result["allocation"])


@pytest.mark.parametrize(
    "analysis",
    [
        snapshot(position(), nav="-1"),
        snapshot(position(), status="needs_reconciliation"),
        snapshot(position(), nav="1"),
        snapshot(position(), nav="NaN"),
    ],
)
def test_incoherent_snapshot_is_rejected(analysis):
    with pytest.raises(ValueError, match="reconciled"):
        run(analysis=analysis)


@pytest.mark.parametrize("age", [-1, 300, 3600])
def test_future_and_stale_snapshots_cannot_be_refreshed_by_relabelling(age):
    data = document()
    analysis = snapshot(position())
    captured = NOW - timedelta(seconds=age)
    with pytest.raises(ValueError, match="not_fresh"):
        assess_strategy_account(data, analysis=analysis, captured_at=captured, now=NOW)


def test_zero_confirmed_capital_is_not_a_zero_division_or_a_purchase():
    result = run(analysis=snapshot(nav="0", cash="0", blocked="0"))
    assert all(row["current_percent"] is None for row in result["allocation"])
    assert result["proposed_trades"] == []


def test_duplicate_positions_or_metadata_fail_closed():
    duplicate = snapshot(position(), position(), cash="80000")
    duplicate_metadata = (metadata(), metadata())
    with pytest.raises(ValueError, match="duplicate_position"):
        run(analysis=duplicate)
    with pytest.raises(ValueError, match="ambiguous_metadata"):
        run(metadata=duplicate_metadata)


def test_verified_same_issuer_and_group_are_aggregated_not_counted_as_diversification():
    positions = (position("a", value="4000"), position("b", value="4000"))
    mappings = tuple(
        IssuerEvidence(
            uid,
            "issuer",
            "group",
            "https://issuer.example/report",
            NOW,
            "https://issuer.example/issue",
            "https://issuer.example/group",
        )
        for uid in ("a", "b")
    )
    result = run(analysis=snapshot(*positions, cash="92000"), mappings=mappings)
    rows = checks(result)
    assert rows["max_instrument_percent"]["state"] == "evaluated"
    assert rows["max_issuer_percent"]["state"] == "blocked"
    assert rows["max_issuer_percent"]["value"]["rub"] == "8000"
    assert rows["max_group_percent"]["value"]["rub"] == "8000"


@pytest.mark.parametrize("when", [NOW - timedelta(days=31), NOW + timedelta(seconds=1)])
def test_missing_stale_and_future_mapping_never_pass_group_cap(when):
    mapping = IssuerEvidence(
        "bond-a",
        "issuer",
        "group",
        "https://issuer.example/report",
        when,
        "https://issuer.example/issue",
        "https://issuer.example/group",
    )
    result = run(mappings=(mapping,))
    assert checks(result)["max_issuer_percent"]["state"] == "unknown"
    assert checks(result)["max_group_percent"]["state"] == "unknown"


def test_partial_known_excess_is_still_blocked():
    result = run(
        analysis=snapshot(
            position(value="40000"), position("b", value=None), cash="50000", status="partial"
        )
    )
    assert checks(result)["max_instrument_percent"]["state"] == "blocked"
    assert checks(result)["max_sector_percent"]["state"] == "blocked"


@pytest.mark.parametrize(
    "agency,symbol,expected",
    [
        ("АКРА", "AAA(RU)", "AAA"),
        ("АКРА", "AA-(RU)", "AA-"),
        ("Эксперт РА", "ruBBB-", "BBB-"),
        ("Эксперт РА", "ruD", "D"),
        ("АКРА", "AA", None),
        ("АКРА", "eAA(RU)", None),
        ("Эксперт РА", "ruA(EXP)", None),
        ("Эксперт РА", "ruAAA.sf", None),
        ("Fitch", "AAA", None),
        ("unknown", "ruAAA", None),
    ],
)
def test_rating_notches_preserve_scale_modifiers_and_reject_unsupported(agency, symbol, expected):
    rating = TBankRating(agency, symbol, NOW, "stable", False)
    assert rating_notch(rating, NOW) == expected
    assert rating_notch(replace(rating, rating_date=NOW + timedelta(seconds=1)), NOW) is None
    assert rating_notch(replace(rating, rating_date=NOW - timedelta(days=367)), NOW) is None


def test_each_notch_cap_and_low_grade_permission_are_independent():
    data = document()
    data["rules"]["rating_caps"]["BB+"] = "20"
    data["policy"]["max_below_grade_percent"] = "20"
    rating = TBankRating("Эксперт РА", "ruBB+", NOW, "negative", True)
    result = run(data, ratings={"bond-a": (rating,)})
    rows = checks(result)
    assert rows["rating_caps.BB+"]["state"] == "evaluated"
    assert rows["max_below_grade_percent"]["state"] == "evaluated"
    assert rows["allow_below_investment_grade"]["state"] == "blocked"
    assert result["ratings"][0]["evidence"][0]["level"] == "ruBB+"
    assert result["ratings"][0]["rating_object"] == "issuer"


def test_credit_unknown_never_silently_becomes_aaa():
    result = run(ratings={"bond-a": (TBankRating("Fitch", "AAA", NOW, "stable", False),)})
    rows = checks(result)
    assert rows["max_unknown_percent"]["state"] == "blocked"
    assert rows["rating_caps.AAA"]["state"] == "unknown"
    assert result["ratings"][0]["notch"] == "NR"


def test_funds_without_lookthrough_do_not_pass_underlying_company_sector_or_credit_checks():
    result = run(analysis=snapshot(position("fund", "etf", "10000"), cash="90000"))
    rows = checks(result)
    for key in (
        "max_issuer_percent",
        "max_group_percent",
        "max_sector_percent",
        "max_below_grade_percent",
        "rating_caps.AAA",
    ):
        assert rows[key]["state"] == "unknown"


def test_horizon_and_max_term_use_calendar_months():
    data = document()
    data["profile"]["horizon_months"] = "1"
    data["policy"]["max_term_months"] = "2"
    result = run(data, metadata=(metadata(maturity=NOW.replace(month=11, day=7)),))
    assert checks(result)["horizon_months"]["state"] == "blocked"
    assert checks(result)["max_term_months"]["state"] == "evaluated"


def test_unknown_terms_cannot_pass_and_editing_locks_are_not_trade_locks():
    data = document()
    data["locked"] = ["bonds"]
    result = run(data)
    assert checks(result)["horizon_months"]["state"] == "unknown"
    assert checks(result)["locked"]["state"] == "inapplicable"


def test_excluded_current_class_is_not_sold_and_conflicting_targets_are_exposed():
    data = document()
    data["excluded"] = ["bonds"]
    data["allocation"] = {"shares": 50, "bonds": 0, "funds": 0, "cash": 50}
    result = run(data)
    assert checks(result)["excluded"]["state"] == "blocked"
    assert checks(result)["target_conflict.shares"]["state"] == "blocked"
    assert result["proposed_trades"] == []


def test_read_only_assessment_does_not_change_any_saved_parameter():
    data = document()
    before = repr(data)
    run(data)
    assert repr(data) == before


def test_unknown_class_cap_is_not_silently_treated_as_zero():
    data = document()
    data["policy"]["max_bond_percent"] = None
    result = checks(run(data))
    assert result["max_bond_percent"]["state"] == "unknown"
    assert "target_conflict.bonds" not in result


def test_unvalued_bond_does_not_pass_term_check():
    result = run(
        analysis=snapshot(position(value=None), nav="100000", cash="90000"), metadata=(metadata(),)
    )
    assert checks(result)["horizon_months"]["state"] == "unknown"
    assert checks(result)["max_term_months"]["state"] == "unknown"


@pytest.mark.parametrize(
    "field,issuer_state,group_state",
    [
        ("source_url", "unknown", "unknown"),
        ("mapping_source_url", "unknown", "unknown"),
        ("group_source_url", "evaluated", "unknown"),
    ],
)
@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://issuer.example/a",
        "javascript:alert(1)",
        "https://user:secret@issuer.example/a",
        "https://x:bad/a",
    ],
)
def test_each_relationship_requires_its_own_source(field, issuer_state, group_state, url):
    data = document()
    data["policy"]["max_issuer_percent"] = "20"
    mapping = IssuerEvidence(
        "bond-a",
        "issuer",
        "group",
        "https://issuer.example/report",
        NOW,
        "https://issuer.example/issue",
        "https://issuer.example/group",
    )
    result = run(data, mappings=(replace(mapping, **{field: url}),))
    assert checks(result)["max_issuer_percent"]["state"] == issuer_state
    assert checks(result)["max_group_percent"]["state"] == group_state


def test_duplicate_mapping_with_invalid_source_is_still_ambiguous():
    first = IssuerEvidence("bond-a", "issuer", "group", "", NOW, "", "")
    duplicate = replace(
        first,
        source_url="https://issuer.example/report",
        mapping_source_url="https://issuer.example/issue",
    )
    mappings = (first, duplicate)
    with pytest.raises(ValueError, match="ambiguous_issuer"):
        run(mappings=mappings)
