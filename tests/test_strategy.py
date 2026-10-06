"""Exact catalog/draft contracts and scenario mathematics, without market claims."""

from copy import deepcopy
from decimal import Decimal

import pytest

from omnicio.strategy import (
    ALLOCATION_KEYS,
    CATALOG_VERSION,
    RATING_LEVELS,
    document_hash,
    expected_shortfall,
    normalize_document,
    preset_document,
    strategy_catalog,
    validate_selection,
)


@pytest.mark.parametrize("preset", strategy_catalog()["presets"], ids=lambda p: p["id"])
def test_all_ten_templates_are_complete_exact_and_not_probabilities(preset):
    document = normalize_document(preset["document"])
    assert sum(document["allocation"].values()) == 100
    assert set(document["allocation"]) == set(ALLOCATION_KEYS)
    assert set(document["rules"]["rating_caps"]) == set(RATING_LEVELS)
    assert document["profile"]["reserve_rub"] is None
    assert document["profile"]["planned_withdrawal_rub"] is None
    assert document["policy"]["securities_tax_rate_percent"] is None
    assert document["profile"]["allow_below_investment_grade"] is False
    assert all(document["rules"]["rating_caps"][key] == "0" for key in ("D", "SD", "RD", "NR"))
    assert validate_selection(document, intent="select") == document
    assert preset["probability_of_profit"] is None
    assert preset["calibration"] == "not_calibrated"


def test_catalog_cannot_be_mutated_by_consumer_and_has_distinct_templates():
    first = strategy_catalog()
    assert len(first["presets"]) == 10
    assert len({item["id"] for item in first["presets"]}) == 10
    assert len({document_hash(item["document"]) for item in first["presets"]}) == 10
    first["presets"][0]["document"]["policy"]["max_issuer_percent"] = "99"
    first["sources"][0]["url"] = "https://invalid.test/"
    assert strategy_catalog()["presets"][0]["document"]["policy"]["max_issuer_percent"] == "5"
    assert "invalid.test" not in strategy_catalog()["sources"][0]["url"]


def test_catalog_matches_the_ten_requested_mandates_without_invented_results():
    catalog = strategy_catalog()
    assert [item["title"] for item in catalog["presets"]] == [
        "Сбалансированная",
        "Консервативная",
        "Агрессивная",
        "Доходная",
        "Накопление",
        "Стратегия Баффета",
        "Стратегия Богла",
        "Стратегия Далио",
        "Лестница облигаций",
        "Дивидендная",
    ]
    assert "sample_illustration" not in catalog
    assert len({item["selection_rules"]["ranking"] for item in catalog["presets"]}) == 10


@pytest.mark.parametrize("legacy", ["near_goal", "floating"])
def test_saved_legacy_mandate_keeps_its_exact_parameters_and_identity(legacy):
    from omnicio.strategy import strategy_rule_set

    saved = preset_document("income")
    saved.update(base_preset_id=legacy, catalog_version="2026-10-06.1", customized=True)
    saved["allocation"] = {"shares": 0, "bonds": 80, "funds": 10, "cash": 10}
    saved["profile"]["reserve_rub"] = "41234.12345678"
    before = deepcopy(saved)
    assert normalize_document(saved) == before
    assert validate_selection(saved, intent="edit") == before
    assert document_hash(normalize_document(saved)) == document_hash(before)
    assert strategy_rule_set(legacy)["ranking"] != "positive_momentum"
    with pytest.raises(ValueError, match="preset_unknown"):
        validate_selection(saved, intent="select")
    saved["catalog_version"] = CATALOG_VERSION
    with pytest.raises(ValueError, match="preset_unknown"):
        normalize_document(saved)


def test_edit_always_creates_personal_copy_and_does_not_rewrite_template():
    document = preset_document("balanced")
    document["profile"]["reserve_rub"] = "12345.12345678"
    changed = validate_selection(document, intent="edit")
    assert changed["customized"] is True
    assert changed["profile"]["reserve_rub"] == "12345.12345678"
    assert preset_document("balanced")["profile"]["reserve_rub"] is None
    # Reverting the value does not silently restore the template label.
    changed["profile"]["reserve_rub"] = None
    assert validate_selection(changed, intent="edit")["customized"] is True


def test_select_keeps_personal_facts_but_cannot_forge_original_strategy():
    document = preset_document("income")
    document["profile"]["reserve_rub"] = "12.01000000"
    document["policy"]["securities_tax_rate_percent"] = "0"
    selected = validate_selection(document, intent="select")
    assert selected["profile"]["reserve_rub"] == "12.01"
    assert selected["policy"]["securities_tax_rate_percent"] == "0"
    document["policy"]["max_issuer_percent"] = "90"
    with pytest.raises(ValueError, match="preset_mismatch"):
        validate_selection(document, intent="select")


@pytest.mark.parametrize(
    "value",
    [True, 1.2, "NaN", "Infinity", "1e3", "-1", "", "1,2", "1.123456789", "1000000000001", {}, []],
)
def test_untrusted_money_rejected(value):
    document = preset_document("balanced")
    document["profile"]["reserve_rub"] = value
    with pytest.raises(ValueError):
        normalize_document(document)


@pytest.mark.parametrize(
    "path,value",
    [
        (("profile", "max_drawdown_percent"), "2.12345"),
        (("profile", "horizon_months"), "0"),
        (("profile", "horizon_months"), "1.1"),
        (("profile", "allow_below_investment_grade"), "true"),
        (("policy", "max_sector_percent"), "101"),
        (("rules", "yield_floor"), "guaranteed"),
    ],
)
def test_invalid_parameters_are_not_clamped(path, value):
    document = preset_document("balanced")
    document[path[0]][path[1]] = value
    with pytest.raises(ValueError):
        normalize_document(document)


def test_unknown_zero_precision_and_catalog_version():
    document = preset_document("balanced")
    document["profile"]["reserve_rub"] = "00000000000000000000000000000000000.0100"
    assert normalize_document(document)["profile"]["reserve_rub"] == "0.01"
    document["profile"]["reserve_rub"] = "1000000000000.00000000"
    assert normalize_document(document)["profile"]["reserve_rub"] == "1000000000000"
    document["profile"]["max_drawdown_percent"] = "0.1234"
    assert normalize_document(document)["profile"]["max_drawdown_percent"] == "0.1234"
    document["catalog_version"] = CATALOG_VERSION + ".old"
    with pytest.raises(ValueError, match="catalog_changed"):
        normalize_document(document)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["allocation"].update(shares=31),
        lambda d: d["allocation"].update(shares=True),
        lambda d: d.update(locked=["shares", "shares"]),
        lambda d: d.update(excluded=["shares"]),
        lambda d: d.update(user_id="another-person"),
        lambda d: d["rules"]["rating_caps"].update(AAA=None),
    ],
)
def test_sum_flags_owner_injection_and_incomplete_rules_rejected(mutation):
    document = preset_document("balanced")
    mutation(document)
    with pytest.raises(ValueError):
        normalize_document(document)


def test_decimal_hash_stable_and_order_independent():
    a = preset_document("balanced")
    b = deepcopy(a)
    b["policy"]["max_sector_percent"] = "25.0000"
    b["policy"] = dict(reversed(list(b["policy"].items())))
    assert document_hash(normalize_document(a)) == document_hash(normalize_document(b))


def test_cvar_uses_fractional_boundary_not_average_of_whole_tail():
    losses = [Decimal("-100"), Decimal("10"), Decimal("100")]
    weights = [Decimal("0.90"), Decimal("0.06"), Decimal("0.04")]
    # Worst 5%: all 4% at loss 100 and exactly 1% at loss 10.
    assert expected_shortfall(losses, weights) == Decimal("82")
    assert expected_shortfall(list(reversed(losses)), list(reversed(weights))) == Decimal("82")
    assert expected_shortfall([Decimal("-5")], [Decimal(1)]) == Decimal("-5")


@pytest.mark.parametrize(
    "losses,probabilities,confidence",
    [
        ([], [], "0.95"),
        (["1"], ["0.5"], "0.95"),
        (["1", "2"], ["-1", "2"], "0.95"),
        (["NaN"], ["1"], "0.95"),
        (["1"], ["1"], "1"),
    ],
)
def test_cvar_requires_a_valid_explicit_distribution(losses, probabilities, confidence):
    loss_values = list(map(Decimal, losses))
    weights = list(map(Decimal, probabilities))
    alpha = Decimal(confidence)
    with pytest.raises(ValueError):
        expected_shortfall(loss_values, weights, alpha)


def test_precision_check_does_not_round_away_small_nonzero_digits():
    doc = preset_document("balanced")
    doc["profile"]["reserve_rub"] = "10.000000000000000000000000000000001"
    with pytest.raises(ValueError, match="precision"):
        normalize_document(doc)


def test_new_catalog_edition_preserves_readable_saved_documents(monkeypatch):
    from omnicio import strategy

    saved = preset_document("income")
    saved["profile"]["reserve_rub"] = "123456789.12345678"
    custom = validate_selection(saved, intent="edit")
    before = deepcopy(custom)
    original_hash = document_hash(custom)
    monkeypatch.setattr(strategy, "CATALOG_VERSION", "2026-10-07.1")
    catalog = strategy_catalog()
    assert before["catalog_version"] in catalog["compatible_document_versions"]
    assert catalog["version"] in catalog["compatible_document_versions"]
    assert normalize_document(custom) == before
    assert document_hash(normalize_document(custom)) == original_hash
    assert validate_selection(custom, intent="edit") == before
    assert custom == before
    # A new selection uses the current template, without rewriting the saved copy.
    assert preset_document("income")["catalog_version"] == catalog["version"]
    with pytest.raises(ValueError, match="preset_mismatch"):
        validate_selection(before, intent="select")
    malformed = deepcopy(before)
    malformed["policy"]["invented_permission"] = True
    with pytest.raises(ValueError, match="fields_invalid"):
        normalize_document(malformed)
