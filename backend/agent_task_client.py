"""Per-job hybrid inference through the existing guarded client and ledger.

Opt-in integration seam, not installed in the live controller. No broker orders,
new queue, new billing tables, model installation or global environment mutation.
All providers below are trusted, synchronous, in-memory application callbacks;
they must not perform network I/O, open SQLite transactions or accept LLM flags.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
import json
import time
from types import MappingProxyType

if __package__:
    from .ai_budget import MoneyLedger, SCALE, day_key
    from .ai_guarded_client import GuardedAIClient, GuardError, _encoded_messages
    from .ai_jobs import CURRENT_JOB, LeaseLost
    from .agent_runtime_policy import (
        AgentPolicy, Availability, BudgetSnapshot, PolicyError, Target,
        TaskRequest, plan_task,
    )
else:
    from ai_budget import MoneyLedger, SCALE, day_key
    from ai_guarded_client import GuardedAIClient, GuardError, _encoded_messages
    from ai_jobs import CURRENT_JOB, LeaseLost
    from agent_runtime_policy import (
        AgentPolicy, Availability, BudgetSnapshot, PolicyError, Target,
        TaskRequest, plan_task,
    )


@dataclass(frozen=True)
class TaskContext:
    request: TaskRequest
    availability: Availability

    def __post_init__(self):
        if type(self.request) is not TaskRequest or type(self.availability) is not Availability:
            raise PolicyError('agent_invalid_task_context')


def _rub(amount: int) -> str:
    whole, fraction = divmod(amount, SCALE)
    return str(whole) if not fraction else f'{whole}.{fraction:06d}'.rstrip('0')


def _routed_environment(source, policy: AgentPolicy, cloud: bool):
    # This is a private per-call copy, never os.environ or the live service config.
    result = dict(source)
    result['AI_TRANSPORT'] = 'gateway' if cloud else 'local'
    if cloud:
        for name in ('AI_USER_DAILY_RUB', 'AI_PROJECT_DAILY_RUB'):
            result[name] = _rub(policy.daily_cap_micro_rub)
        for name in ('AI_USER_MONTHLY_RUB', 'AI_PROJECT_MONTHLY_RUB'):
            result[name] = _rub(policy.monthly_cap_micro_rub)
    # LOCAL_AI_ENABLED, catalogue/region approval and provider keys are never enabled here.
    return MappingProxyType(result)


class AgentTaskClient:
    """Execute one bounded JSON analysis inside an already claimed AnalysisQueue job.

    `context_provider` binds trusted task/freshness/privacy facts to this call.
    `environment_provider` returns the current approved configuration in memory.
    Changes in relevant configuration or request facts revoke the in-flight result.
    Underlying broker-presence checks remain in force, including for local chat;
    independent broker-free companion chat is deliberately a later integration.
    Hooks are composed with, and cannot replace, the adapter's own checks.
    """
    def __init__(self, user_id: int, connect, *, context_provider: Callable[[], TaskContext],
                 environment_provider: Callable[[], Mapping[str, str]], transport=None,
                 budget_guard=None, before_send=None, after_response=None, route_guard=None):
        if type(user_id) is not int or user_id <= 0:
            raise GuardError('agent_invalid_user')
        if not callable(context_provider) or not callable(environment_provider):
            raise GuardError('agent_context_providers_required')
        self.user_id = user_id
        self.connect = connect
        self.context_provider = context_provider
        self.environment_provider = environment_provider
        self.transport = transport
        self.budget_guard = budget_guard
        self.before_send = before_send
        self.after_response = after_response
        self.route_guard = route_guard

    def _environment(self):
        try:
            values = self.environment_provider()
            if not isinstance(values, Mapping):
                raise ValueError
            result = {}
            for name, value in values.items():
                if type(name) is not str:
                    raise ValueError
                if name.startswith(('AGENT_', 'AI_', 'LOCAL_AI_', 'TIMEWEB_AI_')):
                    if type(value) is not str:
                        raise ValueError
                    result[name] = value
            return result
        except Exception:
            raise GuardError('agent_configuration_unavailable') from None

    def _context(self):
        try:
            value = self.context_provider()
            if type(value) is not TaskContext:
                raise ValueError
            return value
        except Exception:
            raise GuardError('agent_context_unavailable') from None

    def _assert_job_in(self, db, job):
        if CURRENT_JOB.get() != job:
            raise LeaseLost('analysis_worker_lease_lost')
        row = db.execute(
            "SELECT 1 FROM ai_work_jobs WHERE id=? AND owner=? AND user_id=? "
            "AND status='running' AND cancel_requested_at IS NULL AND expires_at>?",
            (*job, self.user_id, int(time.time())),
        ).fetchone()
        if row is None:
            raise LeaseLost('analysis_worker_lease_lost')

    @staticmethod
    def _accept(plan, cloud):
        expected = Target.TIMEWEB_PREFLIGHT if cloud else Target.LOCAL_MODEL
        if plan.target is not expected:
            if plan.target is Target.LOCAL_SERVICE:
                raise GuardError('agent_local_service_handler_required')
            raise GuardError('agent_' + plan.reason)

    def complete_json(self, *, tier, messages, max_output_tokens: int):
        job = CURRENT_JOB.get()
        if (not isinstance(job, tuple) or len(job) != 2 or
                any(type(value) is not str or not 0 < len(value) <= 180 for value in job)):
            raise GuardError('agent_claimed_job_required')
        with closing(self.connect()) as db:
            self._assert_job_in(db, job)
        initial = self._context()
        source = self._environment()
        try:
            policy = AgentPolicy.from_environment(source)
        except PolicyError:
            raise GuardError('agent_invalid_policy') from None
        cloud = initial.request.requires_cloud
        preliminary = plan_task(initial.request, policy, initial.availability)
        # Missing quote is expected here; real counters and the exact quote are
        # checked in route_guard and again under the existing reservation lock.
        if not (cloud and preliminary.reason == 'fresh_budget_required'):
            self._accept(preliminary, cloud)
        frozen_messages = json.loads(_encoded_messages(messages, max_output_tokens))
        env = _routed_environment(source, policy, cloud)
        quoted = []

        def current_context():
            if self._environment() != source:
                raise GuardError('agent_configuration_changed')
            context = self._context()
            if context.request != initial.request:
                raise GuardError('agent_task_context_changed')
            return context

        def admission(context, ceiling, db=None):
            budget = None
            if cloud:
                day = day_key(int(time.time()))
                # Project totals include this user's charges; using them for the
                # narrower envelope is conservative. Reuse ledger calculations.
                daily = MoneyLedger._spent(db, day, None) if db is not None else 0
                monthly = MoneyLedger._monthly_spent(db, day, None) if db is not None else 0
                budget = BudgetSnapshot(daily, monthly, ceiling, True)
            self._accept(plan_task(context.request, policy, context.availability, budget), cloud)

        def check_route(route, ceiling):
            if route.mode != ('gateway' if cloud else 'local'):
                raise GuardError('agent_route_mismatch')
            context = current_context()
            with closing(self.connect()) as db:
                db.execute('BEGIN')
                self._assert_job_in(db, job)
                admission(context, ceiling, db)
            if quoted:
                raise GuardError('agent_multiple_routes_for_attempt')
            quoted.append((route, ceiling))
            if self.route_guard is not None:
                self.route_guard(route, ceiling)

        def atomic_guard(db):
            if self.budget_guard is not None:
                self.budget_guard(db)
            context = current_context()
            self._assert_job_in(db, job)
            if len(quoted) != 1:
                raise GuardError('agent_quote_required')
            admission(context, quoted[0][1], db)

        def before_send():
            if self.before_send is not None:
                self.before_send()
            context = current_context()
            with closing(self.connect()) as db:
                self._assert_job_in(db, job)
            # Own reservation is already counted; do not add its ceiling twice.
            # Exact counters were checked atomically by MoneyLedger.reserve.
            admission(context, quoted[0][1])

        def after_response():
            if self.after_response is not None:
                self.after_response()
            current_context()
            with closing(self.connect()) as db:
                self._assert_job_in(db, job)

        client = GuardedAIClient(
            self.user_id, self.connect, env=env, transport=self.transport,
            route_guard=check_route, budget_guard=atomic_guard,
            before_send=before_send, after_response=after_response,
        )
        # No retry or alternative provider, even for an incomplete response.
        return client.complete_json(tier=tier, messages=frozen_messages,
                                    max_output_tokens=max_output_tokens)
