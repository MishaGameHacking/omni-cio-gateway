from __future__ import annotations

from pathlib import Path

import pytest

from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewScenarioSourceStoreV1,
)
import omni_cio.release.final_decision_review_calculator_registration_v1 as subject


def test_registration_preserves_exact_store_identity_and_is_lazy() -> None:
    store = FinalDecisionReviewScenarioSourceStoreV1()
    registration = subject.register_final_decision_review_calculator_publisher(
        source_store=store
    )
    assert registration.source_store is store
    assert registration.publisher.source_store is store
    assert store.active_bundle_count() == 0
    assert registration.internal_only is True
    assert registration.lazy_registration is True
    assert registration.startup_calculation_called is False
    assert registration.startup_broker_called is False
    assert registration.http_publication_method_created is False
    assert registration.trade_authorized is False
    assert registration.order_created is False
    assert registration.trading_methods is False


def test_registration_forwards_publication_policies() -> None:
    store = FinalDecisionReviewScenarioSourceStoreV1()
    registration = subject.register_final_decision_review_calculator_publisher(
        source_store=store,
        max_source_skew_seconds=12,
        max_publication_delay_seconds=45,
    )
    assert registration.publisher.source_store is store


def test_registration_rejects_wrong_store_type() -> None:
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorRegistrationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_REGISTRATION_STORE_TYPE_INVALID",
    ):
        subject.register_final_decision_review_calculator_publisher(
            source_store=object(),  # type: ignore[arg-type]
        )


def test_registration_contract_rejects_store_identity_substitution() -> None:
    first = FinalDecisionReviewScenarioSourceStoreV1()
    second = FinalDecisionReviewScenarioSourceStoreV1()
    publisher = subject.FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=first
    )
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorRegistrationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_REGISTRATION_STORE_IDENTITY_MISMATCH",
    ):
        subject.FinalDecisionReviewCalculatorRegistrationV1(
            source_store=second,
            publisher=publisher,
        )


def test_registration_contract_rejects_safety_tampering() -> None:
    store = FinalDecisionReviewScenarioSourceStoreV1()
    publisher = subject.FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=store
    )
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorRegistrationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_REGISTRATION_SAFETY_INVARIANT_FAILED",
    ):
        subject.FinalDecisionReviewCalculatorRegistrationV1(
            source_store=store,
            publisher=publisher,
            startup_broker_called=True,
        )


def test_registration_module_contains_no_route_or_broker_write_surface() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_calculator_registration_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "@app.get",
        "@app.post",
        "@app.put",
        "@app.delete",
        ".post_order(",
        ".cancel_order(",
        ".replace_order(",
        "withdraw",
        "transfer",
        "logger.exception",
    )
    assert all(marker not in source for marker in forbidden)
