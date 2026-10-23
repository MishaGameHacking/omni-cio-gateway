"""Only a missing or explicitly empty string catalogue permits legacy routing."""
import json
from datetime import datetime, timezone

import pytest

from backend.ai_route_catalog import CATALOG_KEY, CatalogError, approved_candidates

NOW = int(datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp())


@pytest.mark.parametrize("value", [None, False, 0, 0.0, [], {}, b"", (), True, 1])
def test_non_string_catalog_never_enables_legacy_routes(value):
    env = {CATALOG_KEY: value}
    with pytest.raises(CatalogError):
        approved_candidates("premium", env, now=NOW)


@pytest.mark.parametrize("tier", ["fast", "standard", "premium"])
@pytest.mark.parametrize("env", [{}, {CATALOG_KEY: ""}])
def test_explicit_legacy_configuration_still_works(tier, env):
    candidates = approved_candidates(tier, env, now=NOW)
    assert len(candidates) == 1
    assert candidates[0].label == tier.upper()


@pytest.mark.parametrize("raw", [" ", "null", "false", "0", "[]", "{}"])
def test_nonempty_invalid_json_values_do_not_fall_back(raw):
    env = {CATALOG_KEY: raw}
    with pytest.raises(CatalogError):
        approved_candidates("premium", env, now=NOW)


def test_evaluated_model_catalog_remains_bound_to_configured_model():
    row = {"label": "REVIEWED", "model": "test-model", "tiers": ["premium"],
           "evaluation_id": "synthetic-eval-1", "valid_until": "2026-10-20T00:00:00Z",
           "context_tokens": 8192, "max_output_tokens": 2000,
           "structured_json_verified": True}
    env = {CATALOG_KEY: json.dumps([row]), "AI_MODEL_REVIEWED": "test-model"}
    candidates = approved_candidates("premium", env, now=NOW)
    assert len(candidates) == 1
    assert candidates[0].label == "REVIEWED"
    assert candidates[0].fits(6192, 2000)
    assert not candidates[0].fits(6193, 2000)
