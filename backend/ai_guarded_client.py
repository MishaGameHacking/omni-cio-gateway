"""Timeweb gateway/agent routing with explicit data approval and RUB reservations.

No cloud-admin token fallback, automatic expensive fallback, silent model alias,
redirect, or paid retry. Region values are operator attestations, not geolocation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import math
import os
import re
import time
from urllib.parse import urlsplit
import uuid

import httpx

try:
    from .bounded_ai_response import ACCEPT_ENCODING, ResponseBodyError, read_bounded_body
    from .model_json_limits import checked_model_json_text, ModelJsonLimitError, MAX_MODEL_JSON_BYTES
    from .ai_budget import MoneyLedger, BudgetDenied, micro_rub, token_cost, configured_limits
    from .ai_broker_access import broker_binding, assert_broker_binding, assert_broker_binding_in
    from .ai_route_catalog import approved_candidates, CatalogError
    from .ai_jobs import CURRENT_JOB, AnalysisQueue
    from .monitoring_access import assert_monitoring_access
except ImportError:
    from bounded_ai_response import ACCEPT_ENCODING, ResponseBodyError, read_bounded_body
    from model_json_limits import checked_model_json_text, ModelJsonLimitError, MAX_MODEL_JSON_BYTES
    from ai_budget import MoneyLedger, BudgetDenied, micro_rub, token_cost, configured_limits
    from ai_broker_access import broker_binding, assert_broker_binding, assert_broker_binding_in
    from ai_route_catalog import approved_candidates, CatalogError
    from ai_jobs import CURRENT_JOB, AnalysisQueue
    from monitoring_access import assert_monitoring_access


class GuardError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ModelUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class ModelResult:
    model: str
    data: dict
    usage: ModelUsage


def _reject_nonfinite(_: str):
    raise GuardError('ai_nonfinite_json')


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise GuardError('ai_nonfinite_json')
    mantissa = value.lower().partition('e')[0]
    if parsed == 0 and any(character in '123456789' for character in mantissa):
        raise GuardError('ai_numeric_underflow')
    return parsed


def _unique_json_object(pairs) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardError('ai_duplicate_json_field')
        result[key] = value
    return result


def _model_json(value):
    try:
        text = checked_model_json_text(value)
        return json.loads(text, parse_constant=_reject_nonfinite,
                          parse_float=_finite_float, object_pairs_hook=_unique_json_object)
    except ModelJsonLimitError as error:
        raise GuardError(str(error)) from None
    except RecursionError:
        raise GuardError('ai_json_nesting_exceeded') from None


def _result_content(response: dict) -> dict:
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise GuardError('ai_choices_invalid')
    message = choices[0].get('message')
    if not isinstance(message, dict) or not isinstance(message.get('content'), str):
        raise GuardError('ai_content_invalid')
    try:
        content = _model_json(message['content'])
    except (ValueError, TypeError):
        raise GuardError('ai_content_not_json') from None
    if not isinstance(content, dict):
        raise GuardError('ai_content_not_object')
    return content


MAX_RESPONSE_BYTES = MAX_MODEL_JSON_BYTES
GATEWAY = 'https://api.timeweb.ai/v1'


def reject(code: str) -> None:
    raise GuardError(code)


def validated_url(url: str, mode: str) -> str:
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme == 'https' and not parsed.query and not parsed.fragment and not parsed.username and not parsed.password
        valid = valid and parsed.port is None
    except ValueError:
        valid = False
    if mode == 'gateway':
        valid = valid and url.rstrip('/') == GATEWAY
    elif mode == 'agents':
        valid = valid and bool(re.fullmatch(r'https://agent\.timeweb\.cloud/api/v1/cloud-ai/agents/[A-Za-z0-9_-]{1,128}/v1/?', url))
    else:
        valid = False
    if not valid:
        reject('ai_route_url_not_allowed')
    return url.rstrip('/')


@dataclass(frozen=True)
class Route:
    mode: str
    url: str
    key: str = field(repr=False)
    model: str
    input_rate: int
    output_rate: int
    input_allowance: int
    token_parameter: str
    region: str
    expires_at: int

    @property
    def identifier(self) -> str:
        return hashlib.sha256((self.mode + ':' + self.url + ':' + self.model).encode()).hexdigest()


def configured_route(tier, env=None, *, at: int | None = None,
                     input_bytes: int = 0, max_output_tokens: int = 1600) -> Route:
    env = os.environ if env is None else env
    now = int(time.time()) if at is None else at
    if type(input_bytes) is not int or not 0 <= input_bytes <= 110_000:
        reject('ai_context_size_invalid')
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 4000:
        reject('ai_output_limit_invalid')
    try:
        candidates = approved_candidates(str(tier.value), env, now=now)
    except (CatalogError, AttributeError) as error:
        reject(str(error) if isinstance(error, CatalogError) else 'ai_route_invalid_tier')
    eligible = []
    for candidate in candidates:
        route = _configured_label(candidate.label, env, now)
        if candidate.fits(input_bytes + route.input_allowance, max_output_tokens):
            ceiling = token_cost(input_bytes + route.input_allowance, max_output_tokens,
                                 route.input_rate, route.output_rate)
            eligible.append((ceiling, route.identifier, route))
    if not eligible:
        reject('ai_no_route_with_context_capacity')
    # Selection is before dispatch. Never retry a possibly charged request on
    # another model; the existing ledger/reconciliation rules remain authoritative.
    return min(eligible, key=lambda item: (item[0], item[1]))[2]


def _configured_label(label: str, env, now: int) -> Route:
    prefix = 'AI_' + label + '_'
    mode = env.get(prefix + 'TRANSPORT', env.get('AI_TRANSPORT', 'gateway'))
    if env.get('AI_EXTERNAL_PROCESSING_APPROVED') != 'true':
        reject('ai_processing_approval_required')
    region = env.get(prefix + 'PROCESSING_REGION', '')
    permitted = [part.strip() for part in env.get('AI_ALLOWED_PROCESSING_REGIONS', 'RU').split(',')]
    if (re.fullmatch('[A-Z]{2}', region) is None and region != 'EXTERNAL') or region not in permitted:
        reject('ai_processing_region_not_approved')
    url = env.get('TIMEWEB_AI_BASE_URL', '').strip() or GATEWAY
    key = env.get('TIMEWEB_AI_TOKEN', '').strip()
    if mode == 'agents':
        url = env.get('TIMEWEB_AI_' + label + '_BASE_URL', '').strip()
        key = env.get('TIMEWEB_AI_' + label + '_TOKEN', '').strip()
    url = validated_url(url, mode)
    if not key:
        reject('timeweb_ai_key_missing')
    model = env.get('AI_MODEL_' + label, '').strip()
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}', model) is None:
        reject('ai_model_identifier_missing_or_invalid')
    if env.get(prefix + 'PRICING_MODEL') != model:
        reject('ai_model_price_binding_required')
    input_rate, output_rate, allowance, expires_at = _configured_prices(env, prefix, now)
    parameter = env.get(prefix + 'TOKEN_PARAMETER', '')
    if parameter not in {'max_tokens','max_completion_tokens'}:
        reject('ai_token_parameter_required')
    return Route(mode, url, key, model, input_rate, output_rate, allowance, parameter, region, expires_at)


def _configured_prices(env, prefix, now):
    try:
        expires = datetime.fromisoformat(env.get(prefix + 'PRICING_VALID_UNTIL', '').replace('Z', '+00:00'))
        if expires.tzinfo is None or not now < expires.timestamp() <= now + 7 * 86400:
            raise ValueError
        input_rate = micro_rub(env[prefix + 'INPUT_RUB_PER_MILLION'])
        output_rate = micro_rub(env[prefix + 'OUTPUT_RUB_PER_MILLION'])
        allowance = int(env.get(prefix + 'INPUT_TOKEN_ALLOWANCE', '4096'))
        if input_rate <= 0 or output_rate <= 0 or not 0 <= allowance <= 32000:
            raise ValueError
    except (KeyError, ValueError, BudgetDenied):
        reject('ai_prices_missing_stale_or_invalid')
    return input_rate, output_rate, allowance, int(expires.timestamp())


def _encoded_messages(messages, max_output_tokens):
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 4000:
        reject('ai_output_limit_invalid')
    if not messages or len(messages) > 4:
        reject('ai_messages_invalid')
    for message in messages:
        if not isinstance(message, dict) or set(message) != {'role','content'} or message['role'] not in {'system','user','assistant'} or not isinstance(message['content'], str):
            reject('ai_messages_invalid')
    encoded = json.dumps(list(messages), ensure_ascii=False, allow_nan=False).encode()
    if len(encoded) > 110_000:
        reject('ai_context_too_large')
    return encoded


def _assert_complete_response(response):
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict) or choices[0].get('finish_reason') != 'stop':
        raise GuardError('ai_incomplete_response')


def completion_payload(route: Route, messages, max_output_tokens: int) -> dict:
    payload = {'messages': list(messages), 'stream': False, route.token_parameter: max_output_tokens}
    if route.mode == 'gateway':
        payload['model'] = route.model
        if route.model == 'dashscope/qwen3.5-flash':
            # Provider catalogue exposes this exact parameter; avoid hidden
            # reasoning tokens for bounded fact explanations. No model fallback.
            payload['enable_thinking'] = False
            payload['response_format'] = {'type': 'json_object'}
    return payload


class GuardedAIClient:
    def __init__(self, user_id: int, connect, *, transport=None, env=None,
                 attempt_id=None, budget_guard=None, before_send=None, after_response=None, route_guard=None):
        self.user_id = user_id
        self.connect = connect
        self.env = os.environ if env is None else env
        self.transport = transport
        self.attempt_id = attempt_id
        self.route_guard = route_guard
        self.budget_guard = budget_guard
        self.before_send = before_send
        self.after_response = after_response
        self.ledger = MoneyLedger(connect)
        self.ledger.initialize()

    def check_ready(self, tier, *, input_bytes: int = 0, max_output_tokens: int = 1600) -> Route:
        route = configured_route(tier, self.env, input_bytes=input_bytes, max_output_tokens=max_output_tokens)
        try:
            if any(cap <= 0 for cap in configured_limits(self.env)):
                reject('ai_ruble_budget_not_enabled')
            broker_binding(self.connect, self.user_id)
        except BudgetDenied as error:
            raise GuardError(str(error)) from None
        return route

    def complete_json(self, *, tier, messages, max_output_tokens: int):
        try:
            return self._complete(tier, messages, max_output_tokens)
        except BudgetDenied as error:
            raise GuardError(str(error)) from None

    def _reserve_guard(self, binding):
        def check(db):
            if self.budget_guard is not None:
                self.budget_guard(db)
            assert_broker_binding_in(db, self.user_id, binding)
        return check

    def _complete(self, tier, messages, max_output_tokens: int):
        assert_monitoring_access(self.connect)
        encoded = _encoded_messages(messages, max_output_tokens)
        route = self.check_ready(tier, input_bytes=len(encoded), max_output_tokens=max_output_tokens)
        # Conservative configurable estimate, not a tokenizer/invoice guarantee.
        input_bound = len(encoded) + route.input_allowance
        ceiling = token_cost(input_bound, max_output_tokens, route.input_rate, route.output_rate)
        if self.route_guard is not None:
            self.route_guard(route, ceiling)
        # Reject changed quotes before acquiring a new connection-bound attempt.
        # Readiness already checked presence; bind the version only after the
        # caller accepts this exact route and conservative cost ceiling.
        binding = broker_binding(self.connect, self.user_id)
        job = CURRENT_JOB.get()
        if job:
            queue = AnalysisQueue(self.connect)
            queue.assert_owner(*job)
            if queue.has_uncertain(self.user_id):
                reject('ai_worker_reconciliation_required')
        attempt = self.attempt_id or (job[0] if job else uuid.uuid4().hex)
        reservation = hashlib.sha256((attempt + ':' + tier.value + ':' + route.identifier).encode()).hexdigest()
        user_cap, project_cap, user_month_cap, project_month_cap = configured_limits(self.env)
        self.ledger.reserve(user_id=self.user_id, key=reservation, route=route.identifier, model=route.model,
                            ceiling=ceiling, user_cap=user_cap, project_cap=project_cap,
                            job=job, guard=self._reserve_guard(binding),
                            user_month_cap=user_month_cap, project_month_cap=project_month_cap)
        payload = completion_payload(route, messages, max_output_tokens)
        sent = False
        try:
            if job:
                AnalysisQueue(self.connect).assert_owner(*job)
            assert_monitoring_access(self.connect)
            if self.before_send is not None:
                self.before_send()
            assert_broker_binding(self.connect, self.user_id, binding)
            if int(time.time()) >= route.expires_at:
                reject('ai_prices_missing_stale_or_invalid')
            # Once dispatch may have begun, no timeout/cancellation can refund
            # an unknown provider charge or cause an automatic paid replay.
            sent = True
            response = self._send(route, payload)
            usage, returned = self._account_usage(response, route, reservation, input_bound, max_output_tokens)
            # Accounting happens even if the content/JSON validation below fails.
            _assert_complete_response(response)
            content = _result_content(response)
            if job:
                AnalysisQueue(self.connect).assert_owner(*job)
            if self.after_response is not None:
                self.after_response()
            assert_broker_binding(self.connect, self.user_id, binding)
            return ModelResult(model=returned, data=content, usage=usage)
        except Exception:
            if sent:
                self.ledger.cool_down(route.identifier)
            else:
                # This process knows dispatch never happened. Cancellation at
                # the pre-send guard may release its unused reservation.
                self.ledger.settle(reservation, model=route.model, cost=0,
                                   input_tokens=0, output_tokens=0)
            raise
        finally:
            # No refund for timeouts, missing usage or interrupted workers.
            self.ledger.uncertain(reservation)

    def _account_usage(self, response, route, reservation, input_bound, output_bound):
        """Keep charge evidence even when token bounds invalidate the answer."""
        usage = self._usage(response)
        returned = response.get('model')
        try:
            cost = token_cost(usage.prompt_tokens, usage.completion_tokens, route.input_rate, route.output_rate)
        except BudgetDenied:
            self.ledger.uncertain(reservation, pause_reason='unexpected_usage')
            raise
        if usage.prompt_tokens > input_bound or usage.completion_tokens > output_bound:
            self.ledger.uncertain(reservation, pause_reason='usage_over_ceiling', observed_cost=cost)
            raise GuardError('ai_usage_outside_reserved_bounds')
        if not self.ledger.settle(reservation, model=returned, cost=cost,
                                  input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens):
            raise GuardError('ai_usage_requires_reconciliation')
        return usage, returned

    def _send(self, route: Route, payload: dict) -> dict:
        deadline = time.monotonic() + 60
        try:
            with (
                httpx.Client(timeout=httpx.Timeout(45, connect=10), follow_redirects=False,
                              transport=self.transport) as client,
                client.stream('POST', route.url + '/chat/completions',
                                   headers={'Authorization': 'Bearer ' + route.key, 'Accept': 'application/json',
                                            'Accept-Encoding': ACCEPT_ENCODING},
                                   json=payload) as response,
            ):
                if response.status_code != 200:
                    raise GuardError('ai_http_' + str(response.status_code), retryable=False)
                data = read_bounded_body(response, limit=MAX_RESPONSE_BYTES,
                                         deadline=deadline, clock=time.monotonic)
            parsed = _model_json(data)
            if not isinstance(parsed, dict):
                raise ValueError
            return parsed
        except ResponseBodyError as error:
            raise GuardError(str(error), retryable=False) from None
        except httpx.HTTPError:
            raise GuardError('ai_transport_outcome_unknown', retryable=False) from None
        except ValueError:
            raise GuardError('ai_response_not_json') from None

    @staticmethod
    def _usage(response: dict):
        usage = response.get('usage')
        if not isinstance(usage, dict):
            raise GuardError('ai_usage_missing')
        values = [usage.get(key) for key in ('prompt_tokens','completion_tokens','total_tokens')]
        if any(type(value) is not int or not 0 <= value <= 1_000_000 for value in values):
            raise GuardError('ai_usage_invalid')
        if values[0] + values[1] != values[2] or values[0] == 0:
            raise GuardError('ai_usage_inconsistent')
        return ModelUsage(*values)


