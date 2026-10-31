"""Opt-in integration of the existing portfolio analysis flow with AgentTaskClient.

No new scheduler/table, model installation, live trade or service reconfiguration.
The server chooses the route; source text and model output cannot grant permission.
Receipts use existing workspace_records and contain hashes/metadata, not prompts.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing
from datetime import datetime
import hashlib
import json
import os
import re
import time

if __package__:
    from .ai_budget import transaction
    from .ai_broker_access import broker_binding_in
    from .ai_guarded_client import GuardedAIClient, GuardError, _encoded_messages
    from .ai_jobs import CURRENT_JOB, LeaseLost
    from .ai_policy import AnalysisDecision
    from .agent_runtime_policy import AgentPolicy, Availability, TaskKind, TaskRequest
    from .agent_task_client import AgentTaskClient, TaskContext, _routed_environment
    from .analysis_engine import SYSTEM_PROMPT, _canonical_context
else:  # The supported uvicorn app:app entry point uses top-level sibling modules.
    from ai_budget import transaction
    from ai_broker_access import broker_binding_in
    from ai_guarded_client import GuardedAIClient, GuardError, _encoded_messages
    from ai_jobs import CURRENT_JOB, LeaseLost
    from ai_policy import AnalysisDecision
    from agent_runtime_policy import AgentPolicy, Availability, TaskKind, TaskRequest
    from agent_task_client import AgentTaskClient, TaskContext, _routed_environment
    from analysis_engine import SYSTEM_PROMPT, _canonical_context

RECEIPT_KIND = 'agent_analysis_admission_v1'
MAX_SNAPSHOT_AGE_SECONDS = 300
SECRET_FIELD = re.compile(r'token|password|secret|authorization|api.?key|credential|cookie|private.?key', re.I)
IDENTITY_FIELDS = frozenset({'accountId', 'account_id', 'brokerAccountId', 'clientId',
    'client_id', 'telegram_id', 'telegramId', 'username', 'email', 'phone', 'picture',
    'address', 'fullName'})


def _enabled(env):
    value = env.get('AGENT_ROUTING_ENABLED', 'false')
    if value not in ('true', 'false'):
        raise GuardError('agent_routing_flag_invalid')
    return value == 'true'


def _route(env):
    value = env.get('AGENT_PORTFOLIO_ROUTE', 'local')
    if value not in ('local', 'timeweb'):
        raise GuardError('agent_portfolio_route_invalid')
    return value


def _copy_context(context):
    try:
        result = json.loads(_canonical_context(context))
    except (TypeError, ValueError, RecursionError):
        raise GuardError('agent_analysis_context_invalid') from None
    if set(result) != {'portfolio', 'profile', 'computed', 'sources'}:
        raise GuardError('agent_analysis_context_invalid')
    pending = [(result, 0)]
    visited = 0
    while pending:
        value, depth = pending.pop()
        visited += 1
        if depth > 16 or visited > 16000:
            raise GuardError('agent_analysis_context_invalid')
        if isinstance(value, dict):
            for key in list(value):
                if SECRET_FIELD.search(key):
                    raise GuardError('agent_secret_input_blocked')
                if key in IDENTITY_FIELDS:
                    del value[key]
                else:
                    pending.append((value[key], depth + 1))
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
    portfolio = result['portfolio']
    if not isinstance(portfolio, dict) or not isinstance(result['profile'], dict) or not isinstance(result['computed'], dict):
        raise GuardError('agent_analysis_context_invalid')
    accounts = portfolio.get('accounts', [])
    if not isinstance(accounts, list):
        raise GuardError('agent_analysis_context_invalid')
    for number, account in enumerate(accounts, 1):
        if not isinstance(account, dict):
            raise GuardError('agent_analysis_context_invalid')
        account.pop('id', None)
        account.pop('name', None)
        account['account_ref'] = f'account-{number}'
    # Holdings remain sensitive. Removing direct account labels is not anonymity
    # or a general-purpose DLP detector; explicit cloud approval is still required.
    return result


def _instant(value):
    if not isinstance(value, str) or len(value) > 80:
        raise GuardError('agent_source_time_invalid')
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError
        return stamp.timestamp()
    except (ValueError, OverflowError):
        raise GuardError('agent_source_time_invalid') from None


def _source_deadline(context, now):
    sources = context.get('sources')
    if not isinstance(sources, list) or not 1 <= len(sources) <= 128:
        raise GuardError('agent_fresh_sources_required')
    if not isinstance(sources[0], dict) or sources[0].get('provider') != 'T-Invest API':
        raise GuardError('agent_portfolio_source_required')
    deadlines = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or source.get('fresh') is not True:
            raise GuardError('agent_fresh_sources_required')
        observed = _instant(source.get('as_of'))
        if observed > now + 5:
            raise GuardError('agent_source_from_future')
        if index == 0:
            deadlines.append(observed + MAX_SNAPSHOT_AGE_SECONDS)
        if source.get('expires_at') is not None:
            deadlines.append(_instant(source['expires_at']))
        elif index:
            # No expiry means the caller has not established validity of an older
            # third-party source; use the same conservative short interval.
            deadlines.append(observed + MAX_SNAPSHOT_AGE_SECONDS)
    deadline = min(deadlines)
    if deadline <= now:
        raise GuardError('agent_fresh_sources_required')
    return deadline


def _job_in(db, user_id, job):
    if (type(user_id) is not int or user_id <= 0 or not isinstance(job, tuple) or len(job) != 2
            or any(type(item) is not str or not 0 < len(item) <= 180 for item in job)
            or CURRENT_JOB.get() != job):
        raise GuardError('agent_claimed_job_required')
    row = db.execute("SELECT 1 FROM ai_work_jobs WHERE id=? AND owner=? AND user_id=? "
        "AND status='running' AND cancel_requested_at IS NULL AND expires_at>?",
        (*job, user_id, int(time.time()))).fetchone()
    if row is None:
        raise LeaseLost('analysis_worker_lease_lost')


def _stored(db, user_id, job):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspace_records'").fetchone():
        return None
    return db.execute('SELECT payload_json,version FROM workspace_records WHERE user_id=? AND kind=? AND id=?',
                      (user_id, RECEIPT_KIND, job[0])).fetchone()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


class AnalysisTaskAdapter:
    """Controller-compatible client, bound to one trusted analysis payload."""
    def __init__(self, user_id, connect, context, decision, environment_provider,
                 *, budget_guard=None, before_send=None):
        if type(decision) is not AnalysisDecision or decision.tier.value not in ('fast', 'standard', 'premium'):
            raise GuardError('agent_analysis_decision_invalid')
        self.user_id, self.connect, self.decision = user_id, connect, decision
        self.environment_provider = environment_provider
        self.job = CURRENT_JOB.get()
        self.context = _copy_context(context)
        self.deadline = _source_deadline(self.context, time.time())
        env = dict(environment_provider())
        if not _enabled(env):
            raise GuardError('agent_routing_disabled')
        self.mode = _route(env)
        self.cloud = self.mode == 'timeweb'
        self.policy = AgentPolicy.from_environment(env)
        self.approved = env.get('AI_EXTERNAL_PROCESSING_APPROVED') == 'true'
        if self.cloud and (not self.policy.cloud_enabled or not self.approved):
            raise GuardError('agent_cloud_not_approved')
        self.original_budget_guard = budget_guard
        self.original_before_send = before_send
        self._messages_json = _json([
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': _json({'analysis_reason': decision.reason.value,
                'notify_user': decision.notify_user, 'context': self.context})},
        ])
        with transaction(connect) as db:
            _job_in(db, user_id, self.job)
            if budget_guard is not None:
                budget_guard(db)
            self.binding = broker_binding_in(db, user_id)
            self.receipt = _json({'version': 1, 'route': self.mode, 'kind': 'portfolio_review',
                'request_sha256': hashlib.sha256(self._messages_json.encode()).hexdigest(),
                'context_sha256': hashlib.sha256(_json(self.context).encode()).hexdigest(),
                'broker_binding': self.binding,
                'source_deadline': self.deadline, 'tier': decision.tier.value,
                'reason': decision.reason.value, 'max_output_tokens': decision.max_output_tokens})
            existing = _stored(db, user_id, self.job)
            if existing is not None:
                if existing[0] != self.receipt or existing[1] != 1:
                    raise GuardError('agent_analysis_receipt_changed')
            else:
                now = int(time.time())
                db.execute('INSERT INTO workspace_records(user_id,kind,id,payload_json,version,created_at,updated_at) '
                           'VALUES(?,?,?,?,1,?,?)', (user_id, RECEIPT_KIND, self.job[0], self.receipt, now, now))

    @property
    def messages(self):
        # A caller may inspect a copy, never change the admitted request in place.
        return json.loads(self._messages_json)

    def _environment(self):
        values = self.environment_provider()
        if not isinstance(values, Mapping) or not _enabled(values) or _route(values) != self.mode:
            raise GuardError('agent_routing_changed')
        return values

    def _task_context(self):
        return TaskContext(TaskRequest(TaskKind.PORTFOLIO_REVIEW, requires_cloud=self.cloud,
            cloud_data_approved=self.approved, sources_fresh=time.time() < self.deadline),
            # Admission hints only. GuardedAIClient checks the actual local socket,
            # configured route, catalogue, token and prices before dispatch.
            Availability(local_model_ready=True, cloud_route_ready=True))

    def _assert_receipt_in(self, db):
        _job_in(db, self.user_id, self.job)
        row = _stored(db, self.user_id, self.job)
        if row is None or row[0] != self.receipt or row[1] != 1:
            raise GuardError('agent_analysis_receipt_changed')
        if broker_binding_in(db, self.user_id) != self.binding:
            raise GuardError('agent_analysis_broker_changed')
        if time.time() >= self.deadline:
            raise GuardError('agent_fresh_sources_required')
        self._environment()

    def _atomic_guard(self, db):
        if self.original_budget_guard is not None:
            self.original_budget_guard(db)
        self._assert_receipt_in(db)

    def _before(self):
        if self.original_before_send is not None:
            self.original_before_send()
        with closing(self.connect()) as db:
            self._assert_receipt_in(db)

    def _after(self):
        with closing(self.connect()) as db:
            self._assert_receipt_in(db)

    def check_ready(self, tier):
        if tier != self.decision.tier:
            raise GuardError('agent_analysis_decision_changed')
        self._before()
        env = self._environment()
        policy = AgentPolicy.from_environment(env)
        if self.cloud and (not policy.cloud_enabled or env.get('AI_EXTERNAL_PROCESSING_APPROVED') != 'true'):
            raise GuardError('agent_cloud_not_approved')
        client = GuardedAIClient(self.user_id, self.connect,
                                env=_routed_environment(env, policy, self.cloud))
        return client.check_ready(tier, input_bytes=len(_encoded_messages(self.messages, self.decision.max_output_tokens)),
                                  max_output_tokens=self.decision.max_output_tokens)

    def complete_json(self, *, tier, messages, max_output_tokens):
        frozen = json.loads(_encoded_messages(messages, max_output_tokens))
        if tier != self.decision.tier or max_output_tokens != self.decision.max_output_tokens or frozen != self.messages:
            raise GuardError('agent_analysis_payload_changed')
        self._before()
        return AgentTaskClient(self.user_id, self.connect,
            context_provider=self._task_context, environment_provider=self._environment,
            budget_guard=self._atomic_guard, before_send=self._before,
            after_response=self._after).complete_json(tier=tier, messages=frozen,
                                                     max_output_tokens=max_output_tokens)


def build_analysis_client(user_id, connect, *, context, decision,
                          environment_provider=lambda: os.environ,
                          legacy_factory=GuardedAIClient, budget_guard=None, before_send=None):
    """Used by run_user_analysis; off by default until isolated acceptance/deployment.

    A bound job cannot revert to the legacy client by disabling the feature.
    Unbound legacy jobs keep their existing behaviour when the feature is off.
    """
    env = environment_provider()
    if not _enabled(env):
        job = CURRENT_JOB.get()
        if job is not None:
            with closing(connect()) as db:
                if _stored(db, user_id, job) is not None:
                    raise GuardError('agent_routing_changed')
        return legacy_factory(user_id, connect, budget_guard=budget_guard, before_send=before_send), context
    adapter = AnalysisTaskAdapter(user_id, connect, context, decision, environment_provider,
                                  budget_guard=budget_guard, before_send=before_send)
    return adapter, adapter.context
