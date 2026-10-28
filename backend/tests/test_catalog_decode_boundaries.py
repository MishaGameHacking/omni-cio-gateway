"""Malformed operator configuration must fail closed with a catalog error."""
from datetime import datetime, timezone
import json
from unittest.mock import patch

import pytest
from backend import ai_route_catalog as catalog

NOW = int(datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp())


def choose(raw):
    return catalog.approved_candidates("fast", {catalog.CATALOG_KEY: raw}, now=NOW)


def test_unencodable_unicode_has_a_catalog_error():
    with pytest.raises(catalog.CatalogError, match="encoding_invalid"):
        choose("\ud800")


def test_decoder_recursion_has_a_catalog_error():
    with patch.object(catalog.json, "loads", side_effect=RecursionError("decoder depth")):
        with pytest.raises(catalog.CatalogError, match="json_invalid"):
            choose("[]")


@pytest.mark.parametrize("raw", ["[" * 15000 + "]" * 15000, "x" * 32001, "\u0410" * 16001],
                         ids=["nested-under-byte-limit", "ascii-over-limit", "utf8-over-limit"])
def test_size_and_depth_do_not_fall_back_to_default_route(raw):
    with pytest.raises(catalog.CatalogError):
        choose(raw)


def test_valid_bound_model_is_still_admitted():
    entry = {"label": "FAST_LOCAL", "model": "test-model", "tiers": ["fast"],
             "evaluation_id": "synthetic-fixture", "valid_until": "2026-10-20T00:00:00Z",
             "context_tokens": 8192, "max_output_tokens": 1600,
             "structured_json_verified": True}
    env = {catalog.CATALOG_KEY: json.dumps([entry]), "AI_MODEL_FAST_LOCAL": "test-model"}
    approved = catalog.approved_candidates("fast", env, now=NOW)
    assert approved == (catalog.Candidate("FAST_LOCAL", 8192, 1600),)


def test_absent_configuration_keeps_explicit_legacy_slot():
    assert choose("") == (catalog.Candidate("FAST"),)
