from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.validation import (
    WalkForwardDatasetV1,
    WalkForwardFoldV1,
    WalkForwardMode,
    WalkForwardObservationV1,
    WalkForwardValidationBlocker,
    WalkForwardValidationPlanV1,
    WalkForwardValidationPolicyV1,
    WalkForwardValidationStatus,
    WalkForwardValidationWarning,
)
from omni_cio.validation.walk_forward_v1 import (
    WalkForwardValidationError,
    build_walk_forward_validation_plan,
)


NOW = datetime(2026, 7, 29, 14, 30, tzinfo=timezone.utc)
START = NOW - timedelta(days=100)
KEY = "uid:walk-forward-a"


def _source(
    *,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    retrieved_at: datetime = NOW,
) -> MarketSourceV1:
    return MarketSourceV1(
        provider="synthetic-validation-source",
        authority=authority,
        retrieved_at=retrieved_at,
        source_id="validation-dataset-v1",
    )


def _observations(
    *,
    count: int = 70,
    label_horizon: timedelta = timedelta(hours=12),
) -> tuple[WalkForwardObservationV1, ...]:
    rows: list[WalkForwardObservationV1] = []
    for index in range(count):
        decision_at = START + timedelta(days=index)
        label_end = decision_at + label_horizon
        rows.append(
            WalkForwardObservationV1(
                observation_id=f"observation-{index:03d}",
                instrument_key=KEY,
                feature_window_start=decision_at - timedelta(days=20),
                feature_window_end=decision_at - timedelta(minutes=1),
                feature_data_available_at=decision_at - timedelta(minutes=1),
                universe_snapshot_at=decision_at - timedelta(days=1),
                decision_at=decision_at,
                label_window_start=decision_at,
                label_window_end=label_end,
                label_data_available_at=label_end,
                source_record_id=f"source-row-{index:03d}",
            )
        )
    return tuple(rows)


def _dataset(
    *,
    count: int = 70,
    label_horizon: timedelta = timedelta(hours=12),
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    source_retrieved_at: datetime = NOW,
) -> WalkForwardDatasetV1:
    return WalkForwardDatasetV1(
        dataset_id="dataset-a",
        instrument_key=KEY,
        source=_source(
            authority=authority,
            retrieved_at=source_retrieved_at,
        ),
        observations=_observations(
            count=count,
            label_horizon=label_horizon,
        ),
    )


def test_expanding_walk_forward_plan_builds_unique_out_of_sample_folds() -> None:
    result = build_walk_forward_validation_plan(
        _dataset(),
        policy=WalkForwardValidationPolicyV1(minimum_folds=4),
        assessed_at=NOW,
    )

    assert result.status is WalkForwardValidationStatus.READY
    assert result.validation_ready is True
    assert result.fold_count == 4
    assert result.out_of_sample_observation_count == 40
    assert result.out_of_sample_coverage == Decimal("40") / Decimal("70")
    assert tuple(fold.train_count for fold in result.folds) == (30, 40, 50, 60)
    assert tuple(fold.test_count for fold in result.folds) == (10, 10, 10, 10)
    test_ids = [
        observation_id
        for fold in result.folds
        for observation_id in fold.test_observation_ids
    ]
    assert len(test_ids) == len(set(test_ids))
    assert result.look_ahead_data_allowed is False
    assert result.test_data_used_for_training is False
    assert result.performance_metrics_computed is False
    assert WalkForwardValidationWarning.EXPANDING_WINDOW in result.warnings


def test_rolling_plan_limits_training_history_without_reusing_test_windows() -> None:
    policy = WalkForwardValidationPolicyV1(
        mode=WalkForwardMode.ROLLING,
        minimum_train_observations=30,
        rolling_train_observations=35,
        test_observations=10,
        step_observations=10,
        minimum_folds=4,
    )

    result = build_walk_forward_validation_plan(
        _dataset(),
        policy=policy,
        assessed_at=NOW,
    )

    assert result.validation_ready is True
    assert tuple(fold.train_count for fold in result.folds) == (30, 35, 35, 35)
    assert WalkForwardValidationWarning.ROLLING_WINDOW in result.warnings


def test_overlapping_labels_are_purged_using_availability_and_embargo() -> None:
    policy = WalkForwardValidationPolicyV1(
        minimum_train_observations=20,
        test_observations=10,
        step_observations=10,
        embargo_seconds=86_400,
        minimum_folds=4,
    )

    result = build_walk_forward_validation_plan(
        _dataset(label_horizon=timedelta(days=5)),
        policy=policy,
        assessed_at=NOW,
    )

    assert result.validation_ready is True
    assert result.fold_count == 4
    assert all(fold.purged_count > 0 for fold in result.folds)
    for fold in result.folds:
        assert (
            fold.latest_train_label_available_at
            + timedelta(seconds=fold.embargo_seconds)
            <= fold.test_decision_start
        )
    assert WalkForwardValidationWarning.OVERLAPPING_LABELS_PURGED in result.warnings


def test_insufficient_dataset_returns_rejected_plan_without_claiming_validation() -> None:
    result = build_walk_forward_validation_plan(
        _dataset(count=35),
        assessed_at=NOW,
    )

    assert result.status is WalkForwardValidationStatus.REJECTED
    assert result.validation_ready is False
    assert result.fold_count == 0
    assert WalkForwardValidationBlocker.INSUFFICIENT_OBSERVATIONS in result.blockers
    assert WalkForwardValidationBlocker.INSUFFICIENT_VALID_FOLDS in result.blockers


def test_untrusted_or_future_dataset_source_blocks_readiness() -> None:
    untrusted = build_walk_forward_validation_plan(
        _dataset(authority=SourceAuthority.SECONDARY),
        policy=WalkForwardValidationPolicyV1(minimum_folds=4),
        assessed_at=NOW,
    )
    assert WalkForwardValidationBlocker.UNTRUSTED_SOURCE in untrusted.blockers
    assert untrusted.fold_count == 4

    future = build_walk_forward_validation_plan(
        _dataset(source_retrieved_at=NOW + timedelta(minutes=10)),
        policy=WalkForwardValidationPolicyV1(minimum_folds=4),
        assessed_at=NOW,
    )
    assert WalkForwardValidationBlocker.SOURCE_RETRIEVED_IN_FUTURE in future.blockers


def test_observation_contract_rejects_look_ahead_and_invalid_labels() -> None:
    observation = _observations(count=1)[0]

    payload = observation.model_dump()
    payload["feature_data_available_at"] = observation.decision_at + timedelta(seconds=1)
    with pytest.raises(ValidationError, match="feature data was unavailable"):
        WalkForwardObservationV1.model_validate(payload)

    payload = observation.model_dump()
    payload["universe_snapshot_at"] = observation.decision_at + timedelta(seconds=1)
    with pytest.raises(ValidationError, match="universe snapshot"):
        WalkForwardObservationV1.model_validate(payload)

    payload = observation.model_dump()
    payload["label_window_start"] = observation.decision_at - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="label window starts"):
        WalkForwardObservationV1.model_validate(payload)

    payload = observation.model_dump()
    payload["label_data_available_at"] = observation.label_window_end - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="label data availability"):
        WalkForwardObservationV1.model_validate(payload)


def test_dataset_contract_rejects_duplicates_order_and_premature_retrieval() -> None:
    rows = list(_observations(count=3))
    duplicate_payload = _dataset(count=3).model_dump()
    duplicate_observations = list(duplicate_payload["observations"])
    duplicate_observations[1] = dict(duplicate_observations[1])
    duplicate_observations[1]["observation_id"] = rows[0].observation_id
    duplicate_payload["observations"] = duplicate_observations
    with pytest.raises(ValidationError, match="IDs must be unique"):
        WalkForwardDatasetV1.model_validate(duplicate_payload)

    ordered_payload = _dataset(count=3).model_dump()
    ordered_observations = list(ordered_payload["observations"])
    ordered_observations[0], ordered_observations[1] = (
        ordered_observations[1],
        ordered_observations[0],
    )
    ordered_payload["observations"] = ordered_observations
    with pytest.raises(ValidationError, match="must be chronological"):
        WalkForwardDatasetV1.model_validate(ordered_payload)

    premature_payload = _dataset(count=3).model_dump()
    premature_payload["source"]["retrieved_at"] = rows[-1].label_data_available_at - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="before labels were available"):
        WalkForwardDatasetV1.model_validate(premature_payload)


def test_policy_rejects_overlapping_test_windows_and_invalid_rolling_mode() -> None:
    with pytest.raises(ValidationError, match="test windows cannot overlap"):
        WalkForwardValidationPolicyV1(
            test_observations=10,
            step_observations=5,
        )

    with pytest.raises(ValidationError, match="requires rolling train size"):
        WalkForwardValidationPolicyV1(mode=WalkForwardMode.ROLLING)

    with pytest.raises(ValidationError, match="below minimum train size"):
        WalkForwardValidationPolicyV1(
            mode=WalkForwardMode.ROLLING,
            minimum_train_observations=30,
            rolling_train_observations=20,
        )


def test_fold_and_plan_tampering_are_rejected() -> None:
    result = build_walk_forward_validation_plan(
        _dataset(),
        policy=WalkForwardValidationPolicyV1(minimum_folds=4),
        assessed_at=NOW,
    )
    first_fold = result.folds[0]

    fold_payload = first_fold.model_dump()
    fold_payload["train_count"] = 999
    with pytest.raises(ValidationError, match="train count"):
        WalkForwardFoldV1.model_validate(fold_payload)

    fold_payload = first_fold.model_dump()
    test_ids = list(fold_payload["test_observation_ids"])
    test_ids[0] = first_fold.train_observation_ids[0]
    fold_payload["test_observation_ids"] = test_ids
    with pytest.raises(ValidationError, match="sets must be disjoint"):
        WalkForwardFoldV1.model_validate(fold_payload)

    plan_payload = result.model_dump()
    plan_payload["out_of_sample_coverage"] = Decimal("0")
    with pytest.raises(ValidationError, match="coverage"):
        WalkForwardValidationPlanV1.model_validate(plan_payload)

    plan_payload = result.model_dump()
    folds = [dict(fold) for fold in plan_payload["folds"]]
    second_test_ids = list(folds[1]["test_observation_ids"])
    second_test_ids[0] = folds[0]["test_observation_ids"][0]
    folds[1]["test_observation_ids"] = second_test_ids
    plan_payload["folds"] = folds
    with pytest.raises(ValidationError, match="cannot repeat"):
        WalkForwardValidationPlanV1.model_validate(plan_payload)


def test_immutable_safety_flags_and_naive_assessment_are_rejected() -> None:
    payload = _dataset().model_dump()
    payload["trading_methods"] = True
    with pytest.raises(ValidationError):
        WalkForwardDatasetV1.model_validate(payload)

    with pytest.raises(
        WalkForwardValidationError,
        match="WALK_FORWARD_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE",
    ):
        build_walk_forward_validation_plan(
            _dataset(),
            assessed_at=datetime(2026, 7, 29, 14, 30),
        )
