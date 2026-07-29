from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from omni_cio.contracts.v1.validation import (
    WalkForwardDatasetV1,
    WalkForwardFoldV1,
    WalkForwardMode,
    WalkForwardValidationBlocker,
    WalkForwardValidationPlanV1,
    WalkForwardValidationPolicyV1,
    WalkForwardValidationStatus,
    WalkForwardValidationWarning,
)


class WalkForwardValidationError(ValueError):
    """The supplied walk-forward planning request is invalid."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise WalkForwardValidationError(
            "WALK_FORWARD_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def build_walk_forward_validation_plan(
    dataset: WalkForwardDatasetV1,
    *,
    policy: WalkForwardValidationPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> WalkForwardValidationPlanV1:
    """Create purged, embargoed, non-overlapping out-of-sample folds."""

    active_policy = policy or WalkForwardValidationPolicyV1()
    evaluation_time = _aware_utc(assessed_at)
    blockers: list[WalkForwardValidationBlocker] = []
    warnings: list[WalkForwardValidationWarning] = [
        WalkForwardValidationWarning.SPLIT_PLAN_ONLY_NO_PERFORMANCE,
        WalkForwardValidationWarning.TRANSACTION_COSTS_NOT_EVALUATED,
        WalkForwardValidationWarning.SINGLE_INSTRUMENT_DATASET,
        WalkForwardValidationWarning.PARAMETER_STABILITY_NOT_ASSESSED,
        (
            WalkForwardValidationWarning.EXPANDING_WINDOW
            if active_policy.mode is WalkForwardMode.EXPANDING
            else WalkForwardValidationWarning.ROLLING_WINDOW
        ),
    ]

    if dataset.source.authority not in active_policy.trusted_authorities:
        _append_unique(blockers, WalkForwardValidationBlocker.UNTRUSTED_SOURCE)
    source_future_seconds = (
        dataset.source.retrieved_at - evaluation_time
    ).total_seconds()
    if source_future_seconds > active_policy.future_tolerance_seconds:
        _append_unique(
            blockers,
            WalkForwardValidationBlocker.SOURCE_RETRIEVED_IN_FUTURE,
        )

    observations = dataset.observations
    minimum_required = (
        active_policy.minimum_train_observations
        + active_policy.test_observations
    )
    if len(observations) < minimum_required:
        _append_unique(
            blockers,
            WalkForwardValidationBlocker.INSUFFICIENT_OBSERVATIONS,
        )

    folds: list[WalkForwardFoldV1] = []
    any_purged = False
    test_start = active_policy.minimum_train_observations
    while test_start + active_policy.test_observations <= len(observations):
        test_rows = observations[
            test_start : test_start + active_policy.test_observations
        ]
        first_test_decision = test_rows[0].decision_at
        cutoff = first_test_decision - timedelta(
            seconds=active_policy.embargo_seconds
        )
        prior_rows = observations[:test_start]
        eligible_train = [
            observation
            for observation in prior_rows
            if observation.label_data_available_at <= cutoff
        ]
        purged_rows = [
            observation
            for observation in prior_rows
            if observation.label_data_available_at > cutoff
        ]
        if purged_rows:
            any_purged = True

        if active_policy.mode is WalkForwardMode.ROLLING:
            rolling_size = active_policy.rolling_train_observations
            if rolling_size is None:
                raise WalkForwardValidationError(
                    "WALK_FORWARD_ROLLING_SIZE_MISSING"
                )
            eligible_train = eligible_train[-rolling_size:]

        if len(eligible_train) >= active_policy.minimum_train_observations:
            latest_label_available = max(
                row.label_data_available_at for row in eligible_train
            )
            folds.append(
                WalkForwardFoldV1(
                    fold_number=len(folds) + 1,
                    train_observation_ids=tuple(
                        row.observation_id for row in eligible_train
                    ),
                    test_observation_ids=tuple(
                        row.observation_id for row in test_rows
                    ),
                    purged_observation_ids=tuple(
                        row.observation_id for row in purged_rows
                    ),
                    train_count=len(eligible_train),
                    test_count=len(test_rows),
                    purged_count=len(purged_rows),
                    train_decision_start=eligible_train[0].decision_at,
                    train_decision_end=eligible_train[-1].decision_at,
                    test_decision_start=test_rows[0].decision_at,
                    test_decision_end=test_rows[-1].decision_at,
                    latest_train_label_available_at=latest_label_available,
                    embargo_seconds=active_policy.embargo_seconds,
                )
            )
        test_start += active_policy.step_observations

    if any_purged:
        _append_unique(
            warnings,
            WalkForwardValidationWarning.OVERLAPPING_LABELS_PURGED,
        )
    if len(folds) < active_policy.minimum_folds:
        _append_unique(
            blockers,
            WalkForwardValidationBlocker.INSUFFICIENT_VALID_FOLDS,
        )

    test_ids = [
        observation_id
        for fold in folds
        for observation_id in fold.test_observation_ids
    ]
    out_of_sample_count = len(test_ids)
    coverage = Decimal(out_of_sample_count) / Decimal(len(observations))
    validation_ready = not blockers
    status = (
        WalkForwardValidationStatus.READY
        if validation_ready
        else WalkForwardValidationStatus.REJECTED
    )
    return WalkForwardValidationPlanV1(
        assessed_at=evaluation_time,
        status=status,
        validation_ready=validation_ready,
        dataset_id=dataset.dataset_id,
        instrument_key=dataset.instrument_key,
        policy=active_policy,
        observation_count=len(observations),
        fold_count=len(folds),
        out_of_sample_observation_count=out_of_sample_count,
        out_of_sample_coverage=coverage,
        folds=tuple(folds),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
