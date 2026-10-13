"""Timeweb gateway/agent routing with explicit data approval and RUB reservations.

No cloud-admin token fallback, automatic expensive fallback, silent model alias,
redirect, or paid retry. Region values are operator attestations, not geolocation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os
import re
import time
from urllib.parse import urlsplit
import uuid

import httpx

try:
    from .ai_budget import MoneyLedger, BudgetDenied, micro_rub, token_cost
    from .ai_jobs import CURRENT_JOB, AnalysisQueue
except ImportError:
    from ai_budget import MoneyLedger, BudgetDenied, micro_rub, token_cost
    from ai_jobs import CURRENT_JOB, AnalysisQueue


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


def _result_content(response: dict) -> dict:
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise GuardError('ai_choices_invalid')
    message = choices[0].get('message')
    if not isinstance(message, dict) or not isinstance(message.get('content'), str):
        raise GuardError('ai_content_invalid')
    try:
        content = json.loads(message['content'], parse_constant=_reject_nonfinite)
    except (ValueError, TypeError):
        raise GuardError('ai_content_not_json') from None
    if not isinstance(content, dict):
        raise GuardError('ai_content_not_object')
    return content


MAX_RESPONSE_BYTES = 512_000
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


def configured_route(tier, env=None, *, at: int | None = None) -> Route:
    env = os.environ if env is None else env
    now = int(time.time()) if at is None else at
    label = str(tier.value).upper()
    if label not in {'FAST','STANDARD','PREMIUM'}:
        reject('ai_route_invalid_tier')
    mode = env.get('AI_TRANSPORT', 'gateway')
    prefix = 'AI_' + label + '_'
    if env.get('AI_EXTERNAL_PROCESSING_APPROVED') != 'true':
        reject('ai_processing_approval_required')
    region = env.get(prefix + 'PROCESSING_REGION', '')
    permitted = [part.strip() for part in env.get('AI_ALLOWED_PROCESSING_REGIONS', 'RU').split(',')]
    if re.fullmatch('[A-Z]{2}', region) is None or region not in permitted:
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
    parameter = env.get(prefix + 'TOKEN_PARAMETER', '')
    if parameter not in {'max_tokens','max_completion_tokens'}:
        reject('ai_token_parameter_required')
    return Route(mode, url, key, model, input_rate, output_rate, allowance, parameter, region, int(expires.timestamp()))


class GuardedAIClient:
    def __init__(self, user_id: int, connect, *, transport=None, env=None):
        self.user_id = user_id
        self.connect = connect
        self.env = os.environ if env is None else env
        self.transport = transport
        self.ledger = MoneyLedger(connect)
        self.ledger.initialize()

    def check_ready(self, tier) -> Route:
        route = configured_route(tier, self.env)
        if micro_rub(self.env.get('AI_USER_DAILY_RUB', '0')) <= 0 or micro_rub(self.env.get('AI_PROJECT_DAILY_RUB', '0')) <= 0:
            reject('ai_ruble_budget_not_enabled')
        return route

    def complete_json(self, *, tier, messages, max_output_tokens: int):
        try:
            return self._complete(tier, messages, max_output_tokens)
        except BudgetDenied as error:
            raise GuardError(str(error)) from None

    def _complete(self, tier, messages, max_output_tokens: int):
        route = self.check_ready(tier)
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 4000:
            reject('ai_output_limit_invalid')
        if not messages or len(messages) > 4:
            reject('ai_messages_invalid')
        for message in messages:
            if set(message) != {'role','content'} or message['role'] not in {'system','user','assistant'} or not isinstance(message['content'], str):
                reject('ai_messages_invalid')
        encoded = json.dumps(list(messages), ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > 110_000:
            reject('ai_context_too_large')
        # Conservative configurable estimate, not a tokenizer/invoice guarantee.
        input_bound = len(encoded) + route.input_allowance
        ceiling = token_cost(input_bound, max_output_tokens, route.input_rate, route.output_rate)
        job = CURRENT_JOB.get()
        if job:
            queue = AnalysisQueue(self.connect)
            queue.assert_owner(*job)
            if queue.has_uncertain(self.user_id):
                reject('ai_worker_reconciliation_required')
        attempt = job[0] if job else uuid.uuid4().hex
        reservation = hashlib.sha256((attempt + ':' + tier.value + ':' + route.identifier).encode()).hexdigest()
        self.ledger.reserve(user_id=self.user_id, key=reservation, route=route.identifier, model=route.model,
                            ceiling=ceiling, user_cap=micro_rub(self.env.get('AI_USER_DAILY_RUB', '0')),
                            project_cap=micro_rub(self.env.get('AI_PROJECT_DAILY_RUB', '0')))
        payload = {'messages': list(messages), 'stream': False, route.token_parameter: max_output_tokens}
        if route.mode == 'gateway':
            payload['model'] = route.model
        try:
            if job:
                AnalysisQueue(self.connect).assert_owner(*job)
            response = self._send(route, payload)
            usage = self._usage(response)
            returned = response.get('model')
            cost = token_cost(usage.prompt_tokens, usage.completion_tokens, route.input_rate, route.output_rate)
            if usage.prompt_tokens > input_bound or usage.completion_tokens > max_output_tokens:
                self.ledger.uncertain(reservation, pause_reason='usage_over_ceiling')
                raise GuardError('ai_usage_outside_reserved_bounds')
            if not self.ledger.settle(reservation, model=returned, cost=cost,
                                      input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens):
                raise GuardError('ai_usage_requires_reconciliation')
            # Accounting happens even if the content/JSON validation below fails.
            choices = response.get('choices')
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict) or choices[0].get('finish_reason') != 'stop':
                raise GuardError('ai_incomplete_response')
            content = _result_content(response)
            if job:
                AnalysisQueue(self.connect).assert_owner(*job)
            return ModelResult(model=returned, data=content, usage=usage)
        except Exception:
            self.ledger.cool_down(route.identifier)
            raise
        finally:
            # No refund for timeouts, missing usage or interrupted workers.
            self.ledger.uncertain(reservation)

    def _send(self, route: Route, payload: dict) -> dict:
        try:
            with httpx.Client(timeout=httpx.Timeout(45, connect=10), follow_redirects=False,
                              transport=self.transport) as client:
                with client.stream('POST', route.url + '/chat/completions',
                                   headers={'Authorization': 'Bearer ' + route.key, 'Accept': 'application/json'},
                                   json=payload) as response:
                    if response.status_code != 200:
                        raise GuardError('ai_http_' + str(response.status_code), retryable=False)
                    data = bytearray()
                    deadline = time.monotonic() + 60
                    for chunk in response.iter_bytes():
                        if time.monotonic() > deadline:
                            raise GuardError('ai_response_deadline')
                        data.extend(chunk)
                        if len(data) > MAX_RESPONSE_BYTES:
                            raise GuardError('ai_response_too_large')
            parsed = json.loads(data, parse_constant=_reject_nonfinite)
            if not isinstance(parsed, dict):
                raise ValueError
            return parsed
        except httpx.HTTPError:
            raise GuardError('ai_transport_outcome_unknown', retryable=False) from None
        except (ValueError, UnicodeError):
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
