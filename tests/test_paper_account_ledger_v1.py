from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.paper import (
    PaperJournalEventKind,
    PaperJournalEventV1,
    PaperOrderStatus,
    PaperPurchaseResultV1,
    PaperRejectReason,
)
from omni_cio.contracts.v1.paper_ledger import (
    PaperAccountLedgerV1,
    PaperLedgerPositionV1,
)
from omni_cio.contracts.v1.paper_sell import PaperSaleResultV1
from omni_cio.paper import PaperAccountLedgerError, build_paper_account_ledger


BASE = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
OTHER_ACCOUNT = AccountReference(masked_id="***9999", account_type="ИИС")


def _metadata(
    schema_name: str,
    retrieved_at: datetime,
    account: AccountReference = ACCOUNT,
) -> ContractMetadata:
    return ContractMetadata(
        schema_name=schema_name,
        retrieved_at=retrieved_at,
        account=account,
        provenance=(
            SourceReference(
                provider="omni-cio-test",
                operation=schema_name,
                retrieved_at=retrieved_at,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _money(amount: str, currency: str = "RUB") -> Money:
    return Money(amount=Decimal(amount), currency=currency)


def _journal(rejected: bool, occurred_at: datetime) -> tuple[PaperJournalEventV1, ...]:
    if rejected:
        return (
            PaperJournalEventV1(
                sequence=1,
                occurred_at=occurred_at,
                kind=PaperJournalEventKind.REJECTED,
                message="Paper result rejected without state change.",
            ),
        )
    return (
        PaperJournalEventV1(
            sequence=1,
            occurred_at=occurred_at,
            kind=PaperJournalEventKind.ACCEPTED,
            message="Paper result accepted.",
        ),
        PaperJournalEventV1(
            sequence=2,
            occurred_at=occurred_at,
            kind=PaperJournalEventKind.FILL,
            message="Paper fill recorded.",
        ),
    )


def _purchase(
    *,
    scenario_id: str = "paper.buy.asset-b",
    retrieved_at: datetime = BASE + timedelta(minutes=1),
    account: AccountReference = ACCOUNT,
    currency: str = "RUB",
    cash_before: str = "1000",
    cash_after: str = "890",
    position_before: int = 0,
    position_after: int = 1,
    lot_size: int = 1,
) -> PaperPurchaseResultV1:
    return PaperPurchaseResultV1(
        metadata=_metadata("paper_purchase_result", retrieved_at, account),
        scenario_id=scenario_id,
        source_preview_schema_version="1.0",
        stable_key="uid:asset-b",
        instrument_uid="asset-b",
        currency=currency,
        status=PaperOrderStatus.FILLED,
        reject_reasons=(),
        requested_lots=1,
        filled_lots=1,
        unfilled_lots=0,
        lot_size=lot_size,
        filled_units=lot_size,
        gross_amount=_money("100", currency),
        commission=_money("2", currency),
        accrued_interest=_money("8", currency),
        total_cost=_money("110", currency),
        paper_cash_before=_money(cash_before, currency),
        paper_cash_after=_money(cash_after, currency),
        position_lots_before=position_before,
        position_lots_after=position_after,
        journal=_journal(False, retrieved_at),
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def _sale(
    *,
    scenario_id: str = "paper.sell.asset-a",
    retrieved_at: datetime = BASE + timedelta(minutes=2),
    account: AccountReference = ACCOUNT,
    currency: str = "RUB",
    cash_before: str = "890",
    cash_after: str = "985",
    position_before: int = 5,
    position_after: int = 4,
    lot_size: int = 1,
) -> PaperSaleResultV1:
    return PaperSaleResultV1(
        metadata=_metadata("paper_sale_result", retrieved_at, account),
        scenario_id=scenario_id,
        source_preview_schema_version="1.0",
        stable_key="uid:asset-a",
        instrument_uid="asset-a",
        currency=currency,
        status=PaperOrderStatus.FILLED,
        reject_reasons=(),
        requested_lots=1,
        filled_lots=1,
        unfilled_lots=0,
        lot_size=lot_size,
        filled_units=lot_size,
        gross_security_proceeds=_money("98", currency),
        accrued_interest_proceeds=_money("2", currency),
        gross_proceeds=_money("100", currency),
        commission=_money("1", currency),
        estimated_tax=_money("4", currency),
        net_proceeds=_money("95", currency),
        paper_cash_before=_money(cash_before, currency),
        paper_cash_after=_money(cash_after, currency),
        position_lots_before=position_before,
        position_lots_after=position_after,
        journal=_journal(False, retrieved_at),
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def _rejected_purchase(
    *,
    scenario_id: str = "paper.buy.rejected",
    retrieved_at: datetime = BASE + timedelta(minutes=3),
) -> PaperPurchaseResultV1:
    return PaperPurchaseResultV1(
        metadata=_metadata("paper_purchase_result", retrieved_at),
        scenario_id=scenario_id,
        source_preview_schema_version="1.0",
        stable_key="uid:asset-b",
        instrument_uid="asset-b",
        currency="RUB",
        status=PaperOrderStatus.REJECTED,
        reject_reasons=(PaperRejectReason.PREVIEW_NOT_READY,),
        requested_lots=1,
        filled_lots=0,
        unfilled_lots=1,
        lot_size=1,
        filled_units=0,
        gross_amount=_money("0"),
        commission=_money("0"),
        accrued_interest=_money("0"),
        total_cost=_money("0"),
        paper_cash_before=_money("985"),
        paper_cash_after=_money("985"),
        position_lots_before=1,
        position_lots_after=1,
        journal=_journal(True, retrieved_at),
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def _initial_positions() -> tuple[PaperLedgerPositionV1, ...]:
    return (
        PaperLedgerPositionV1(
            stable_key="uid:asset-a",
            instrument_uid="asset-a",
            lot_size=1,
            lots=5,
        ),
    )


def test_mixed_purchase_sale_and_rejection_replay_exactly() -> None:
    ledger = build_paper_account_ledger(
        account=ACCOUNT,
        currency="RUB",
        initial_cash=Decimal("1000"),
        initial_positions=_initial_positions(),
        results=(_purchase(), _sale(), _rejected_purchase()),
        built_at=BASE + timedelta(minutes=4),
    )

    assert ledger.final_cash.amount == Decimal("985")
    assert [(position.stable_key, position.lots) for position in ledger.final_positions] == [
        ("uid:asset-a", 4),
        ("uid:asset-b", 1),
    ]
    assert ledger.scenario_ids == (
        "paper.buy.asset-b",
        "paper.sell.asset-a",
        "paper.buy.rejected",
    )
    assert ledger.total_purchase_cost.amount == Decimal("110")
    assert ledger.total_sale_net_proceeds.amount == Decimal("95")
    assert ledger.total_commission.amount == Decimal("3")
    assert ledger.total_estimated_tax.amount == Decimal("4")
    assert ledger.filled_purchase_lots == 1
    assert ledger.filled_sale_lots == 1
    assert ledger.rejected_event_count == 1
    assert [event.sequence for event in ledger.events] == [1, 2, 3]
    assert ledger.paper_only is True
    assert ledger.broker_order_created is False
    assert ledger.execution_ready is False
    assert ledger.trading_methods is False


def test_duplicate_scenario_id_is_rejected_before_replay() -> None:
    with pytest.raises(PaperAccountLedgerError, match="DUPLICATE_PAPER_SCENARIO_ID"):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("1000"),
            initial_positions=_initial_positions(),
            results=(
                _purchase(scenario_id="paper.same"),
                _sale(scenario_id="paper.same"),
            ),
            built_at=BASE + timedelta(minutes=4),
        )


def test_results_must_be_time_ordered_and_build_time_must_be_later() -> None:
    with pytest.raises(
        PaperAccountLedgerError,
        match="PAPER_LEDGER_RESULTS_NOT_TIME_ORDERED",
    ):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("1000"),
            initial_positions=_initial_positions(),
            results=(_sale(retrieved_at=BASE), _purchase()),
            built_at=BASE + timedelta(minutes=4),
        )

    with pytest.raises(
        PaperAccountLedgerError,
        match="PAPER_LEDGER_BUILT_BEFORE_LAST_EVENT",
    ):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("1000"),
            initial_positions=_initial_positions(),
            results=(_purchase(),),
            built_at=BASE,
        )


def test_account_and_currency_mismatch_fail_closed() -> None:
    with pytest.raises(PaperAccountLedgerError, match="PAPER_LEDGER_ACCOUNT_MISMATCH"):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("1000"),
            results=(_purchase(account=OTHER_ACCOUNT),),
            built_at=BASE + timedelta(minutes=4),
        )

    with pytest.raises(PaperAccountLedgerError, match="PAPER_LEDGER_CURRENCY_MISMATCH"):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("1000"),
            results=(
                _purchase(
                    currency="USD",
                    cash_before="1000",
                    cash_after="890",
                ),
            ),
            built_at=BASE + timedelta(minutes=4),
        )


def test_cash_and_position_state_gaps_are_rejected_by_contract() -> None:
    with pytest.raises(ValidationError, match="cash-before state mismatch"):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("999"),
            initial_positions=_initial_positions(),
            results=(_purchase(),),
            built_at=BASE + timedelta(minutes=4),
        )

    with pytest.raises(ValidationError, match="position-before state mismatch"):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("1000"),
            initial_positions=(),
            results=(_sale(cash_before="1000", cash_after="1095"),),
            built_at=BASE + timedelta(minutes=4),
        )


def test_lot_size_and_identity_cannot_change_mid_ledger() -> None:
    changed_lot = _sale(lot_size=2)
    with pytest.raises(ValidationError, match="lot size changed"):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("890"),
            initial_positions=_initial_positions(),
            results=(changed_lot,),
            built_at=BASE + timedelta(minutes=4),
        )

    sale_payload = _sale().model_dump(mode="python")
    sale_payload["instrument_uid"] = "other-asset-a"
    changed_identity = PaperSaleResultV1.model_validate(sale_payload)
    with pytest.raises(ValidationError, match="instrument identity changed"):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("890"),
            initial_positions=_initial_positions(),
            results=(changed_identity,),
            built_at=BASE + timedelta(minutes=4),
        )


def test_zero_lot_position_is_removed_from_final_snapshot() -> None:
    sale = PaperSaleResultV1(
        metadata=_metadata("paper_sale_result", BASE + timedelta(minutes=1)),
        scenario_id="paper.sell.all",
        source_preview_schema_version="1.0",
        stable_key="uid:asset-a",
        instrument_uid="asset-a",
        currency="RUB",
        status=PaperOrderStatus.FILLED,
        reject_reasons=(),
        requested_lots=5,
        filled_lots=5,
        unfilled_lots=0,
        lot_size=1,
        filled_units=5,
        gross_security_proceeds=_money("490"),
        accrued_interest_proceeds=_money("10"),
        gross_proceeds=_money("500"),
        commission=_money("5"),
        estimated_tax=_money("20"),
        net_proceeds=_money("475"),
        paper_cash_before=_money("1000"),
        paper_cash_after=_money("1475"),
        position_lots_before=5,
        position_lots_after=0,
        journal=_journal(False, BASE + timedelta(minutes=1)),
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )
    ledger = build_paper_account_ledger(
        account=ACCOUNT,
        currency="RUB",
        initial_cash=Decimal("1000"),
        initial_positions=_initial_positions(),
        results=(sale,),
        built_at=BASE + timedelta(minutes=2),
    )

    assert ledger.final_positions == ()
    assert ledger.final_cash.amount == Decimal("1475")


def test_initial_positions_must_be_unique_and_event_list_nonempty() -> None:
    duplicate = (*_initial_positions(), *_initial_positions())
    with pytest.raises(
        PaperAccountLedgerError,
        match="DUPLICATE_INITIAL_PAPER_POSITION",
    ):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("1000"),
            initial_positions=duplicate,
            results=(_purchase(),),
            built_at=BASE + timedelta(minutes=4),
        )

    with pytest.raises(PaperAccountLedgerError, match="PAPER_LEDGER_RESULTS_REQUIRED"):
        build_paper_account_ledger(
            account=ACCOUNT,
            currency="RUB",
            initial_cash=Decimal("1000"),
            results=(),
            built_at=BASE + timedelta(minutes=4),
        )


def test_contract_rejects_tampered_final_state_and_scenario_order() -> None:
    ledger = build_paper_account_ledger(
        account=ACCOUNT,
        currency="RUB",
        initial_cash=Decimal("1000"),
        initial_positions=_initial_positions(),
        results=(_purchase(), _sale()),
        built_at=BASE + timedelta(minutes=4),
    )
    cash_payload = ledger.model_dump(mode="python")
    cash_payload["final_cash"]["amount"] = Decimal("9999")
    with pytest.raises(ValidationError, match="final cash"):
        PaperAccountLedgerV1.model_validate(cash_payload)

    scenario_payload = ledger.model_dump(mode="python")
    scenario_payload["scenario_ids"] = tuple(reversed(ledger.scenario_ids))
    with pytest.raises(ValidationError, match="scenario IDs"):
        PaperAccountLedgerV1.model_validate(scenario_payload)


def test_builder_is_deterministic_and_does_not_mutate_inputs() -> None:
    initial = _initial_positions()
    results = (_purchase(), _sale())
    first = build_paper_account_ledger(
        account=ACCOUNT,
        currency="RUB",
        initial_cash=Decimal("1000"),
        initial_positions=initial,
        results=results,
        built_at=BASE + timedelta(minutes=4),
    )
    second = build_paper_account_ledger(
        account=ACCOUNT,
        currency="RUB",
        initial_cash=Decimal("1000"),
        initial_positions=initial,
        results=results,
        built_at=BASE + timedelta(minutes=4),
    )

    assert first == second
    assert initial == _initial_positions()
    assert results[0] == _purchase()
    assert results[1] == _sale()


def test_paper_ledger_has_no_network_persistence_or_execution_surface() -> None:
    source = Path("omni_cio/paper/ledger_v1.py").read_text(encoding="utf-8")
    lowered = source.casefold()
    assert "requests" not in lowered
    assert "httpx" not in lowered
    assert "grpc" not in lowered
    assert "sqlite" not in lowered
    assert "sqlalchemy" not in lowered
    assert "postorder" not in lowered
    assert "trading_methods=true" not in lowered
