"""Operator-approved route labels; prices/secrets stay in the existing config.

Catalog entries are attestations of evaluation, not benchmark results produced
by this module. They never enable a model based on its brand or marketing name.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import json
import re

CATALOG_KEY = "AI_ROUTE_CATALOG_JSON"
TIERS = frozenset({"fast", "standard", "premium"})
FIELDS = frozenset({"label", "model", "tiers", "evaluation_id", "valid_until", "context_tokens", "max_output_tokens", "structured_json_verified"})


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Candidate:
    label: str
    context_tokens: int | None = None
    max_output_tokens: int = 4000

    def fits(self, input_bound: int, output_bound: int) -> bool:
        return output_bound <= self.max_output_tokens and (
            self.context_tokens is None or input_bound + output_bound <= self.context_tokens)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("ai_catalog_duplicate_field")
        result[key] = value
    return result


def _validate_tiers(tiers: object) -> None:
    if not isinstance(tiers, list) or not tiers:
        raise CatalogError("ai_catalog_tiers_invalid")
    # Validate element types before hashing: nested JSON objects/lists are not
    # hashable and must produce an admission error, never an unhandled 500.
    for tier in tiers:
        if not isinstance(tier, str):
            raise CatalogError("ai_catalog_tiers_invalid")
        if tier not in TIERS:
            raise CatalogError("ai_catalog_tiers_invalid")
    if len(set(tiers)) != len(tiers):
        raise CatalogError("ai_catalog_tiers_invalid")


def _valid_entry(row: dict, env: Mapping[str, str], now: int) -> Candidate:
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise CatalogError("ai_catalog_schema_invalid")
    label, model, tiers = row["label"], row["model"], row["tiers"]
    if not isinstance(label, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", label) is None:
        raise CatalogError("ai_catalog_label_invalid")
    if not isinstance(model, str) or not model or model != env.get("AI_MODEL_" + label):
        raise CatalogError("ai_catalog_model_binding_required")
    _validate_tiers(tiers)
    review = row["evaluation_id"]
    if not isinstance(review, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}", review) is None or row["structured_json_verified"] is not True:
        raise CatalogError("ai_catalog_evaluation_required")
    try:
        expires = datetime.fromisoformat(row["valid_until"].replace("Z", "+00:00"))
        if expires.tzinfo is None or not now < expires.timestamp() <= now + 31 * 86400:
            raise ValueError
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise CatalogError("ai_catalog_evaluation_stale") from None
    context, output = row["context_tokens"], row["max_output_tokens"]
    if type(context) is not int or not 256 <= context <= 2_000_000 or type(output) is not int or not 1 <= output <= min(4000, context):
        raise CatalogError("ai_catalog_context_invalid")
    return Candidate(label, context, output)


def approved_candidates(tier: str, env: Mapping[str, str], *, now: int) -> tuple[Candidate, ...]:
    if not isinstance(tier, str) or tier not in TIERS:
        raise CatalogError("ai_route_invalid_tier")
    raw = env.get(CATALOG_KEY, "")
    if not raw:
        return (Candidate(tier.upper()),)  # Existing three-slot configuration.
    if not isinstance(raw, str):
        raise CatalogError("ai_catalog_too_large")
    try:
        byte_count = len(raw.encode("utf-8"))
    except UnicodeEncodeError:
        raise CatalogError("ai_catalog_encoding_invalid") from None
    if byte_count > 32000:
        raise CatalogError("ai_catalog_too_large")
    try:
        rows = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, TypeError, RecursionError) as error:
        raise CatalogError("ai_catalog_json_invalid") from error
    if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
        raise CatalogError("ai_catalog_size_invalid")
    selected, seen = [], set()
    for row in rows:
        candidate = _valid_entry(row, env, now)
        if candidate.label in seen:
            raise CatalogError("ai_catalog_duplicate_route")
        seen.add(candidate.label)
        if tier in row["tiers"]:
            selected.append(candidate)
    if not selected:
        raise CatalogError("ai_no_approved_route_for_task")
    return tuple(selected)
