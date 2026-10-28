"""Catalog admission on synthetic routes, without external model calls."""
from datetime import datetime, timezone
import json

import pytest

from backend.ai_route_catalog import CatalogError, approved_candidates

NOW = 1_792_331_297


def row(label="CHECKED", **changes):
    return {"label": label, "model": "fixture/" + label.lower(), "tiers": ["fast", "standard"],
            "evaluation_id": "synthetic-eval-1", "valid_until": datetime.fromtimestamp(NOW + 86400, timezone.utc).isoformat(),
            "context_tokens": 32000, "max_output_tokens": 1600, "structured_json_verified": True, **changes}


def environment(rows):
    return {"AI_ROUTE_CATALOG_JSON": json.dumps(rows), **{"AI_MODEL_" + r["label"]: r["model"] for r in rows}}


def test_legacy_three_routes_remain_available():
    for tier in ("fast", "standard", "premium"):
        assert approved_candidates(tier, {}, now=NOW)[0].label == tier.upper()


def test_eight_evaluated_candidates_and_task_eligibility():
    rows = [row("MODEL_" + str(i)) for i in range(8)]
    candidates = approved_candidates("standard", environment(rows), now=NOW)
    assert len(candidates) == 8
    env = environment(rows)
    with pytest.raises(CatalogError, match="ai_no_approved_route_for_task"):
        approved_candidates("premium", env, now=NOW)


def test_capacity_includes_input_and_output():
    candidate = approved_candidates("fast", environment([row(context_tokens=1000, max_output_tokens=600)]), now=NOW)[0]
    assert candidate.fits(400, 600)
    assert not candidate.fits(401, 600)
    assert not candidate.fits(1, 601)


@pytest.mark.parametrize("changes,error", [
    ({"evaluation_id": ""}, "evaluation_required"),
    ({"structured_json_verified": False}, "evaluation_required"),
    ({"structured_json_verified": 1}, "evaluation_required"),
    ({"valid_until": "2020-01-01T00:00:00Z"}, "evaluation_stale"),
    ({"valid_until": "2099-01-01T00:00:00Z"}, "evaluation_stale"),
    ({"valid_until": "2026-10-20T12:00:00"}, "evaluation_stale"),
    ({"valid_until": None}, "evaluation_stale"),
    ({"context_tokens": True}, "context_invalid"),
    ({"context_tokens": 100}, "context_invalid"),
    ({"max_output_tokens": 4001}, "context_invalid"),
    ({"max_output_tokens": False}, "context_invalid"),
    ({"tiers": []}, "tiers_invalid"),
    ({"tiers": ["fast", "fast"]}, "tiers_invalid"),
    ({"tiers": ["none"]}, "tiers_invalid"),
    ({"extra": "not-allowed"}, "schema_invalid"),
])
def test_fail_closed_metadata(changes, error):
    env = environment([row(**changes)])
    with pytest.raises(CatalogError, match=error):
        approved_candidates("fast", env, now=NOW)


@pytest.mark.parametrize("label", ["../TOKEN", "x", "MODEL TOKEN", "A" * 33])
def test_label_cannot_select_arbitrary_configuration(label):
    env = environment([row(label)])
    with pytest.raises(CatalogError, match="label_invalid"):
        approved_candidates("fast", env, now=NOW)


def test_model_cannot_reuse_another_models_evaluation():
    env = environment([row()])
    env["AI_MODEL_CHECKED"] = "fixture/changed"
    with pytest.raises(CatalogError, match="model_binding_required"):
        approved_candidates("fast", env, now=NOW)


@pytest.mark.parametrize("raw", ["{", "{}", "[]", "null", "[null]", '[{"label":"A","label":"B"}]', pytest.param("[" + "0," * 20000 + "0]", id="oversized-json")])
def test_invalid_json_catalog(raw):
    with pytest.raises(CatalogError):
        approved_candidates("fast", {"AI_ROUTE_CATALOG_JSON": raw}, now=NOW)


def test_duplicate_and_overlarge_catalog():
    for rows in ([row(), row()], [row("MODEL_" + str(i)) for i in range(33)]):
        env = environment(rows)
        with pytest.raises(CatalogError):
            approved_candidates("fast", env, now=NOW)


@pytest.mark.parametrize("tier", ["none", "auto", "FAST", "unapproved"])
def test_no_implicit_catalog_tier(tier):
    with pytest.raises(CatalogError, match="invalid_tier"):
        approved_candidates(tier, {}, now=NOW)


@pytest.mark.parametrize("tiers", [[[]], [["fast"]], [{}], [None], [True], [1], ["fast", {}], ["fast", ["standard"]]])
def test_nested_or_non_string_tiers_are_admission_errors(tiers):
    env = environment([row(tiers=tiers)])
    with pytest.raises(CatalogError, match="ai_catalog_tiers_invalid"):
        approved_candidates("fast", env, now=NOW)


@pytest.mark.parametrize("tier", [[], {}, None, True])
def test_unhashable_top_level_tier_is_admission_error(tier):
    with pytest.raises(CatalogError, match="ai_route_invalid_tier"):
        approved_candidates(tier, {}, now=NOW)
