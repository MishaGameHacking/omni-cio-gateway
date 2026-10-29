"""Read-only Timeweb AI readiness inspection; never prints API response bodies.

Official schemas (reviewed 2026-10-29): timeweb-cloud/sdk-python/docs/
PaymentsApi.md, Finances.md, AIGatewayApi.md, AiKey.md, AiKeyLimit.md,
AIModelsApi.md, AiProvider.md, ModelV3.md and ModelPriceTier.md. Model prices are RUB per
token; key money limits use the account currency. GET cannot prove either
key-creation rights or that a future creation response will expose its secret.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

BASE = "https://api.timeweb.cloud"
FINANCES = "/api/v1/account/finances"
KEYS = "/api/v1/cloud-ai/ai-keys"
MODELS = "/api/v3/cloud-ai/models"
PROVIDERS = "/api/v1/cloud-ai/providers"
MODEL = "dashscope/qwen3.5-flash"
DEDICATED_PREFIX = "omni-cio-owner55-"
MAX_BYTES = 4 * 1024 * 1024
MAX_DEDICATED_KEYS = 5
MASKED = "hidden-by-api-key-policy"


class InspectionError(Exception):
    """A fixed diagnostic reason, never an API-supplied error message."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def uuid_text(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = str(UUID(value))
    except (ValueError, AttributeError):
        return None
    return parsed if value.lower() == parsed else None


def permitted_path(path):
    if path in {FINANCES, KEYS, MODELS, PROVIDERS}:
        return True
    match = re.fullmatch(re.escape(KEYS) + r"/([0-9a-f-]{36})/entity-limits", path)
    return bool(match and uuid_text(match.group(1)))


class ReadOnlyAPI:
    def __init__(self, token):
        self._token = token
        self._opener = urllib.request.build_opener(NoRedirect())

    def get(self, path):
        if not permitted_path(path):
            raise InspectionError("endpoint_not_allowlisted")
        request = urllib.request.Request(
            BASE + path, method="GET",
            headers={"Authorization": "Bearer " + self._token,
                     "Accept": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=20) as response:
                if response.status != 200:
                    raise InspectionError("unexpected_http_status")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise InspectionError("response_limit_exceeded")
            payload = json.loads(raw, parse_float=Decimal)
        except urllib.error.HTTPError as error:
            reason = {401: "authentication_rejected", 403: "permission_denied",
                      404: "not_found", 429: "rate_limited"}.get(error.code, "http_error")
            raise InspectionError(reason) from None
        except (urllib.error.URLError, OSError):
            raise InspectionError("network_error") from None
        except (ValueError, TypeError):
            raise InspectionError("invalid_json") from None
        if not isinstance(payload, dict):
            raise InspectionError("invalid_response_shape")
        return payload


def has_masked_value(value):
    if isinstance(value, dict):
        return any(has_masked_value(item) for item in value.values())
    if isinstance(value, list):
        return any(has_masked_value(item) for item in value)
    return isinstance(value, str) and value == MASKED


def decimal_text(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        return None
    if len(str(value)) > 64:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0 or number > Decimal("1000000000000"):
        return None
    if positive and number <= 0:
        return None
    if number.as_tuple().exponent < -16:
        return None
    return format(number, "f")


def integer(value, maximum=1_000_000_000):
    return value if type(value) is int and 0 <= value <= maximum else None


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.isoformat() if parsed.tzinfo is not None else None


def complete_collection(payload, name):
    rows = payload.get(name)
    if not isinstance(rows, list) or len(rows) > 10000:
        raise InspectionError("invalid_collection")
    meta = payload.get("meta")
    total = integer(meta.get("total")) if isinstance(meta, dict) else None
    return rows, total == len(rows)


def provider_summary(provider_id, payload):
    report = {"id": integer(provider_id), "metadata_verified": False,
              "type": None, "name_canonical": None}
    if not isinstance(payload, dict) or report["id"] is None:
        return report
    try:
        providers, complete = complete_collection(payload, "providers")
    except InspectionError:
        return report
    matches = [row for row in providers if isinstance(row, dict) and type(row.get("id")) is int
               and row["id"] == provider_id]
    report["matching_provider_count"] = len(matches)
    if len(matches) != 1:
        return report
    row = matches[0]
    report["type"] = row.get("type") if row.get("type") in ("external", "internal") else None
    # Only fixed canonical labels can reach logs; arbitrary catalog text cannot.
    canonical_names = {"dashscope": "DashScope", "alibaba": "Alibaba",
                       "alibaba cloud": "Alibaba Cloud", "timeweb": "Timeweb",
                       "timeweb cloud": "Timeweb Cloud", "qwen": "Qwen"}
    name = row.get("name")
    if isinstance(name, str):
        report["name_canonical"] = canonical_names.get(name.casefold().strip())
    report["metadata_verified"] = complete and report["type"] is not None
    return report


def model_summary(payload, providers=None):
    rows, complete = complete_collection(payload, "models")
    matches = [row for row in rows if isinstance(row, dict) and row.get("model_name") == MODEL]
    report = {"expected_model": MODEL, "catalog_complete": complete,
              "matching_model_count": len(matches), "availability_verified": False,
              "pricing_verified": False, "selection_verified": False,
              "selection_policy": "unique_active_nondeprecated_exact_identifier"}
    report["matching_rows"] = [model_row_summary(row, complete, providers) for row in matches]
    known_states = all(type(row.get("is_stopped")) is bool and type(row.get("is_deprecated")) is bool
                       and row.get("model_type") in ("llm", "hosted-llm")
                       and row.get("catalog_id") is not None for row in report["matching_rows"])
    unique_ids = len({row["catalog_id"] for row in report["matching_rows"]}) == len(matches)
    candidates = [row for row in report["matching_rows"]
                  if row["is_stopped"] is False and row["is_deprecated"] is False]
    report["active_matching_model_count"] = len(candidates)
    report["all_matching_states_recognized"] = known_states
    if not complete or not known_states or not unique_ids or len(candidates) != 1:
        return report
    # Official get_models_v3 includes deprecated/stopped rows and requires checking
    # these flags. A known inactive row is retained as evidence, not another route.
    # Unknown flags/types, duplicate catalog IDs or two active rows never resolve.
    report.update(candidates[0])
    report["selection_verified"] = True
    # Deprecation excludes new-agent selection, but only is_stopped explicitly
    # forbids inference. model_name alone does not prove a cheaper billing route.
    # Bound costs/capacity across every matching non-stopped catalog row.
    routable = [row for row in report["matching_rows"] if row["is_stopped"] is False]
    report["pricing_scope"] = "maximum_all_nonstopped_exact_identifier_rows"
    report["routable_catalog_ids"] = [row["catalog_id"] for row in routable]
    report["pricing_verified"] = all(row["pricing_verified"] is True for row in routable)
    if report["pricing_verified"]:
        for name in ("maximum_input_rub_per_million", "maximum_output_rub_per_million"):
            report[name] = format(max(Decimal(row[name]) for row in routable), "f")
    else:
        report.pop("maximum_input_rub_per_million", None)
        report.pop("maximum_output_rub_per_million", None)
    capacity_verified = True
    for name in ("context_window", "max_output_tokens"):
        capacities = [row.get(name) for row in routable]
        known = all(type(value) is int and value > 0 for value in capacities)
        report[name] = min(capacities) if known else None
        capacity_verified = capacity_verified and known
    report["routable_capacities_verified"] = capacity_verified
    report["capacity_scope"] = "minimum_all_nonstopped_exact_identifier_rows"
    if len(routable) > 1:
        report["max_output_tokens_source"] = "minimum_all_nonstopped_exact_identifier_rows" if report["max_output_tokens"] is not None else "not_declared_for_every_nonstopped_row"
    return report


def parameter_integer(value):
    if isinstance(value, Decimal):
        if not value.is_finite() or value != value.to_integral_value() or not 0 <= value <= 1_000_000_000:
            return None
        return int(value)
    return integer(value)


def generation_parameter_summary(params):
    if not isinstance(params, dict):
        return {}
    result = {}
    for name in ("max_tokens", "max_completion_tokens", "enable_thinking", "response_format"):
        if name not in params:
            continue
        parameter = params[name]
        if not isinstance(parameter, dict):
            result[name] = {"schema_recognized": False}
            continue
        parameter_type = parameter.get("type")
        recognized = parameter_type in ("number", "integer", "boolean", "bool", "enum", "object", "string")
        detail = {"schema_recognized": recognized, "type": parameter_type if recognized else None}
        if name in ("max_tokens", "max_completion_tokens"):
            detail.update({"minimum": parameter_integer(parameter.get("min")),
                           "maximum": parameter_integer(parameter.get("max")),
                           "default": parameter_integer(parameter.get("default"))})
        if name == "enable_thinking":
            detail["default"] = parameter.get("default") if type(parameter.get("default")) is bool else None
            choices = parameter.get("enum")
            detail["boolean_enum"] = choices if isinstance(choices, list) and len(choices) <= 2 and all(type(value) is bool for value in choices) else None
        result[name] = detail
    return result


def model_row_summary(row, complete, providers):
    model_type = row.get("type")
    version = row.get("version")
    numeric_version = version if isinstance(version, str) and re.fullmatch(r"[0-9]{1,8}(?:[.-][0-9]{1,8}){0,4}", version) else None
    report = {"catalog_id": integer(row.get("id")), "pricing_verified": False,
                   "numeric_version": numeric_version,
                   "version_is_null": "version" in row and version is None,
                   "version_format_recognized": numeric_version is not None,
                   "model_type": model_type if model_type in (
                       "llm", "hosted-llm", "embedding", "image", "audio", "video", "moderation", "system-one") else None,
                   "provider": provider_summary(row.get("provider_id"), providers),
                   "is_stopped": row.get("is_stopped") if type(row.get("is_stopped")) is bool else None,
                   "is_deprecated": row.get("is_deprecated") if type(row.get("is_deprecated")) is bool else None,
                   "created_at": timestamp(row.get("created_at")),
                   "updated_at": timestamp(row.get("updated_at")),
                   "deprecation_date": timestamp(row.get("deprecation_date")),
                   "availability_verified": complete and row.get("is_stopped") is False
                   and row.get("is_deprecated") is False and model_type in ("llm", "hosted-llm")}
    values = row.get("parameter_values")
    if not isinstance(values, dict):
        return report
    unit = values.get("pricing_unit", "token")
    in_rate = decimal_text(values.get("cost_in"), positive=True)
    out_rate = decimal_text(values.get("cost_out"), positive=True)
    cache_read = decimal_text(values.get("cost_cache_read"))
    cache_write = decimal_text(values.get("cost_cache_write"))
    cache_prices_valid = ("cost_cache_read" not in values or cache_read is not None) and (
        "cost_cache_write" not in values or cache_write is not None)
    report.update({"pricing_currency": "RUB", "pricing_unit": "token" if unit == "token" else None,
                   "input_rub_per_token": in_rate, "output_rub_per_token": out_rate,
                   "cache_read_rub_per_token": cache_read,
                   "cache_write_rub_per_token": cache_write,
                   "cache_prices_verified": cache_prices_valid,
                   "context_window": integer(values.get("context_window")),
                   "max_output_tokens": integer(values.get("max_output_tokens"))})
    params = row.get("params_info")
    parameter_details = generation_parameter_summary(params)
    report["generation_parameters"] = parameter_details
    report["documented_generation_parameters"] = sorted(set(params) & {
        "max_tokens", "max_completion_tokens", "enable_thinking", "response_format"
    }) if isinstance(params, dict) else []
    catalog_cap = report["max_output_tokens"]
    token_parameter = parameter_details.get("max_tokens", {})
    parameter_cap = token_parameter.get("maximum") if token_parameter.get("type") in ("number", "integer") else None
    minimum_tokens = token_parameter.get("minimum")
    if parameter_cap is not None and minimum_tokens is not None and parameter_cap < minimum_tokens:
        parameter_cap = None
    catalog_cap_invalid = values.get("max_output_tokens") is not None and (catalog_cap is None or catalog_cap <= 0)
    declared_caps = [value for value in (catalog_cap, parameter_cap) if value is not None and value > 0]
    report["max_output_tokens_catalog"] = catalog_cap
    report["max_output_tokens"] = min(declared_caps) if declared_caps and not catalog_cap_invalid else None
    report["max_output_tokens_source"] = (
        "invalid_catalog_limit" if catalog_cap_invalid
        else "minimum_of_declared_catalog_and_max_tokens_limits" if len(declared_caps) == 2
        else "parameter_values.max_output_tokens" if catalog_cap is not None and catalog_cap > 0
        else "params_info.max_tokens.max" if parameter_cap is not None and parameter_cap > 0
        else "not_declared")
    # The catalog lists parameters configurable for agents, not the full gateway
    # API. AiGatewayChatCompletionRequest.md documents response_format passthrough;
    # Alibaba qwen-structured-output lists Qwen3.5-Flash JSON Object non-thinking.
    report["adapter_documentation"] = {
        "response_format_json_object_supported": True,
        "requires_enable_thinking_false": True,
        "requires_json_word_in_prompt": True,
        "live_inference_verified": False,
        "gateway_schema": "https://github.com/timeweb-cloud/sdk-python/blob/main/docs/AiGatewayChatCompletionRequest.md",
        "provider_schema": "https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output",
    }
    tiers = row.get("price_tiers")
    tiers_valid = isinstance(tiers, list) and len(tiers) <= 32
    safe_tiers = []
    last_threshold = -1
    if tiers_valid:
        for tier in tiers:
            if not isinstance(tier, dict):
                tiers_valid = False
                break
            threshold = integer(tier.get("above_context_tokens"))
            input_price = decimal_text(tier.get("cost_in"), positive=True)
            output_price = decimal_text(tier.get("cost_out"), positive=True)
            if threshold is None or threshold <= last_threshold or input_price is None or output_price is None:
                tiers_valid = False
                break
            last_threshold = threshold
            safe_tiers.append({"above_context_tokens": threshold,
                               "input_rub_per_token": input_price,
                               "output_rub_per_token": output_price})
    report["price_tiers_verified"] = tiers_valid
    report["price_tiers"] = safe_tiers if tiers_valid else []
    report["pricing_verified"] = complete and report["catalog_id"] is not None and unit == "token" and in_rate is not None and out_rate is not None and tiers_valid and cache_prices_valid
    if report["pricing_verified"]:
        input_ceiling = max([Decimal(in_rate)] + [Decimal(tier["input_rub_per_token"]) for tier in safe_tiers]
                            + [Decimal(rate) for rate in (cache_read, cache_write) if rate is not None])
        output_ceiling = max([Decimal(out_rate)] + [Decimal(tier["output_rub_per_token"]) for tier in safe_tiers])
        report["maximum_input_rub_per_million"] = format(input_ceiling * 1_000_000, "f")
        report["maximum_output_rub_per_million"] = format(output_ceiling * 1_000_000, "f")
    return report


def key_summary(row):
    name = row.get("name")
    key_id = uuid_text(row.get("id"))
    if not isinstance(name, str) or re.fullmatch(re.escape(DEDICATED_PREFIX) + r"[A-Za-z0-9_-]{1,64}", name) is None:
        return None
    fallback = row.get("fallback_models")
    return {"id": key_id, "name": name,
            "entity_type": row.get("entity_type") if row.get("entity_type") in {"aikey", "k8s"} else None,
            "is_readonly": row.get("is_readonly") if type(row.get("is_readonly")) is bool else None,
            "created_at": timestamp(row.get("created_at")),
            "expires_at": timestamp(row.get("expires_at")),
            "expiry_is_unlimited": "expires_at" in row and row["expires_at"] is None,
            "fallback_disabled_verified": isinstance(fallback, list) and not fallback}


def limits_summary(payload, key_id):
    rows, complete = complete_collection(payload, "ai_key_entity_limits")
    result = []
    for row in rows[:100]:
        if not isinstance(row, dict):
            continue
        result.append({
            "id": uuid_text(row.get("id")),
            "key_binding_verified": row.get("ai_key_id") == key_id and row.get("entity_id") == key_id,
            "entity_type": row.get("entity_type") if row.get("entity_type") in {"aikey", "k8s"} else None,
            "limit_type": row.get("limit_type") if row.get("limit_type") in {"hour", "day", "week", "month"} else None,
            "all_models": "model_id" in row and row["model_id"] is None,
            "model_id": integer(row.get("model_id")),
            "money_limit_account_currency": decimal_text(row.get("money_limit")),
            "token_limit": integer(row.get("limit"), maximum=10**15),
            "expire_at": timestamp(row.get("expire_at")),
        })
    return {"complete": complete and len(rows) <= 100 and len(result) == len(rows), "limits": result}


def inspect(api):
    report = {"read_only": True, "api_methods": ["GET"], "paid_inference_calls_made": False,
              "configuration_changed": False, "account_currency_rub_confirmed": False,
              "create_permission_verified": False, "key_response_unmasked_verified": False,
              "key_response_masking_policy": "not_exposed_by_documented_read_endpoints",
              "hidden_policy_sentinel_observed": False, "read_flags": {},
              "dedicated_key_prefix": DEDICATED_PREFIX, "dedicated_keys": [],
              "checked_at_utc": datetime.now(timezone.utc).isoformat()}

    def read(label, path):
        try:
            payload = api.get(path)
        except InspectionError as error:
            report["read_flags"][label] = {"readable": False, "reason": str(error)}
            return None
        report["read_flags"][label] = {"readable": True, "reason": "http_200"}
        report["hidden_policy_sentinel_observed"] |= has_masked_value(payload)
        return payload

    finances = read("account_currency", FINANCES)
    if finances is not None:
        data = finances.get("finances")
        report["account_currency_rub_confirmed"] = isinstance(data, dict) and data.get("currency") == "RUB"
    models = read("model_catalog", MODELS)
    if models is not None:
        providers = read("provider_catalog", PROVIDERS)
        try:
            report["model"] = model_summary(models, providers)
        except InspectionError:
            report["model"] = {"availability_verified": False, "pricing_verified": False, "reason": "invalid_collection"}
    keys = read("key_metadata", KEYS)
    if keys is not None:
        try:
            rows, complete = complete_collection(keys, "ai_keys")
            dedicated = [item for row in rows if isinstance(row, dict) and (item := key_summary(row)) is not None]
            report["dedicated_key_count"] = len(dedicated)
            report["key_collection_complete"] = complete
            report["dedicated_key_metadata_truncated"] = len(dedicated) > MAX_DEDICATED_KEYS
            for index, key in enumerate(dedicated[:MAX_DEDICATED_KEYS]):
                if key["id"] is not None:
                    limits = read("dedicated_key_" + str(index) + "_limits", KEYS + "/" + key["id"] + "/entity-limits")
                    if limits is not None:
                        try:
                            key["limit_metadata"] = limits_summary(limits, key["id"])
                        except InspectionError:
                            key["limit_metadata"] = {"complete": False, "limits": []}
                report["dedicated_keys"].append(key)
        except InspectionError:
            report["key_collection_complete"] = False
    return report


def main():
    report = {"read_only": True, "configuration_changed": False, "paid_inference_calls_made": False}
    token = os.environ.get("TIMEWEB_CLOUD_TOKEN", "").strip()
    report["cloud_credential_present"] = bool(token)
    if os.environ.get("COMPUTERNAME") != "LAPTOP-NPSGA016":
        report["reason"] = "owner_laptop_required"
    elif not token or len(token) > 8192 or any(character.isspace() for character in token):
        report["reason"] = "protected_credential_missing_or_invalid"
    else:
        try:
            report.update(inspect(ReadOnlyAPI(token)))
            report["reason"] = "inspection_complete"
        except Exception:
            # Never interpolate exceptions: network libraries may carry headers or bodies.
            report["reason"] = "inspection_failed_without_sensitive_output"
    print("OWNER55_AI_INSPECTION=" + json.dumps(report, ensure_ascii=True, sort_keys=True), flush=True)
    return 0 if report.get("reason") == "inspection_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
