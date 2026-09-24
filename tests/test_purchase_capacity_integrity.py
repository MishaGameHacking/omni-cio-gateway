from omni_cio.pretrade import purchase_capacity_integrity_v1 as purchase_capacity_integrity


def base_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "version": "3.7.1",
        "request": {
            "instrument_uid": "e6123145-9665-43e0-8413-cd61b8aa9b13",
            "price_basis": "best_ask",
            "quantity_lots": 3,
            "direction": "ORDER_DIRECTION_BUY",
        },
        "instrument": {
            "name": "Сбер Банк",
            "ticker": "SBER",
            "instrument_type": "share",
            "instrument_kind": "INSTRUMENT_TYPE_SHARE",
            "lot": 1,
            "currency": "rub",
        },
        "market_price": {
            "status": "ok",
            "basis": "best_ask",
            "price": "271.28",
            "currency": "RUB",
            "lot_size": 1,
        },
        "own_funds": {
            "status": "ok",
            "currency": "RUB",
            "buy_money_amount": "1000",
            "buy_max_lots": 3,
            "buy_max_market_lots": 3,
        },
        "order_preview": {
            "status": "ok",
            "lots_requested": 3,
            "initial_order_amount": {
                "amount": "813.84",
                "currency": "RUB",
            },
            "total_order_amount": {
                "amount": "816.29",
                "currency": "RUB",
            },
            "executed_commission": {
                "amount": "2.45",
                "currency": "RUB",
            },
            "executed_commission_rub": {
                "amount": "2.45",
                "currency": "RUB",
            },
            "service_commission": {
                "amount": "0",
                "currency": "RUB",
            },
            "deal_commission": {
                "amount": "2.45",
                "currency": "RUB",
            },
        },
        "affordable": "yes",
        "affordability_confirmed": True,
        "remaining_cash_estimate": "183.71",
        "remaining_cash_currency": "RUB",
        "quality": {
            "complete": True,
            "read_only": True,
            "no_order_created": True,
        },
        "warnings": [],
        "trading_methods": False,
    }


def test_integrity_confirms_happy_path_and_prevents_double_counting() -> None:
    payload = purchase_capacity_integrity.apply_purchase_capacity_integrity(
        base_payload()
    )

    commission = payload["commission_summary"]
    assert commission["canonical_source"] == "executed_commission"
    assert commission["canonical_commission"] == {
        "amount": "2.45",
        "currency": "RUB",
    }
    assert commission["fields_are_additive"] is False
    assert commission["double_count_protection"] is True
    assert commission["naive_sum_if_incorrectly_added"]["amount"] == "7.35"
    assert commission["overstatement_prevented"]["amount"] == "4.9"

    calculations = payload["calculation_checks"]
    assert calculations["initial_order_amount"]["status"] == "passed"
    assert calculations["total_order_amount"]["status"] == "passed"
    assert calculations["remaining_cash"]["status"] == "passed"
    assert calculations["overall_status"] == "passed"
    assert calculations["integrity_confirmed"] is True

    assert payload["currency_consistency"]["status"] == "ok"
    assert payload["limit_summary"]["selected_limit_field"] == "buy_max_lots"
    assert payload["limit_summary"]["selected_limit_value"] == "3"
    assert payload["integrity_status"] == "ok"
    assert payload["quality"]["calculation_integrity_confirmed"] is True


def test_currency_mismatch_blocks_integrity_confirmation() -> None:
    source = base_payload()
    source["own_funds"]["currency"] = "USD"

    payload = purchase_capacity_integrity.apply_purchase_capacity_integrity(source)

    assert payload["currency_consistency"]["status"] == "warning"
    assert payload["currency_consistency"]["unique_currencies"] == ["RUB", "USD"]
    assert payload["calculation_checks"]["integrity_confirmed"] is False
    assert payload["integrity_status"] == "warning"
    assert payload["quality"]["currency_consistent"] is False


def test_bond_uses_returned_aci_once_and_skips_simple_price_formula() -> None:
    source = base_payload()
    source["instrument"].update(
        {
            "name": "Тестовая облигация",
            "ticker": "BOND",
            "instrument_type": "bond",
            "instrument_kind": "INSTRUMENT_TYPE_BOND",
        }
    )
    source["request"]["quantity_lots"] = 1
    source["market_price"].update(
        {
            "price": "101.5",
            "lot_size": 1,
        }
    )
    source["own_funds"].update(
        {
            "buy_money_amount": "1000",
            "buy_max_lots": 1,
            "buy_max_market_lots": 1,
        }
    )
    source["order_preview"] = {
        "status": "ok",
        "lots_requested": 1,
        "initial_order_amount": {
            "amount": "980",
            "currency": "RUB",
        },
        "total_order_amount": {
            "amount": "992",
            "currency": "RUB",
        },
        "executed_commission": {
            "amount": "2",
            "currency": "RUB",
        },
        "extra_bond": {
            "aci_value": {
                "amount": "10",
                "currency": "RUB",
            }
        },
    }
    source["remaining_cash_estimate"] = "8"

    payload = purchase_capacity_integrity.apply_purchase_capacity_integrity(source)

    calculations = payload["calculation_checks"]
    assert calculations["initial_order_amount"]["status"] == "not_applicable"
    assert calculations["total_order_amount"]["status"] == "passed"
    assert calculations["total_order_amount"]["expected"] == "992"
    assert calculations["remaining_cash"]["status"] == "passed"
    assert calculations["integrity_confirmed"] is True


def test_component_commissions_are_used_only_as_a_fallback() -> None:
    source = base_payload()
    source["order_preview"].pop("executed_commission")
    source["order_preview"].pop("executed_commission_rub")
    source["order_preview"]["service_commission"] = {
        "amount": "0.5",
        "currency": "RUB",
    }
    source["order_preview"]["deal_commission"] = {
        "amount": "1.95",
        "currency": "RUB",
    }

    payload = purchase_capacity_integrity.apply_purchase_capacity_integrity(source)

    commission = payload["commission_summary"]
    assert commission["canonical_source"] == "service_plus_deal_fallback"
    assert commission["canonical_commission"] == {
        "amount": "2.45",
        "currency": "RUB",
    }
    assert payload["calculation_checks"]["total_order_amount"]["status"] == "passed"
