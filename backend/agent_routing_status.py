"""Configuration diagnostics for the route actually selected by the worker.

No completion, reservation, source collection or trading is triggered here.
Configuration readiness is deliberately NOT live inference or job admission.
The endpoint may run existing schema initialization before calling this helper.
"""
from __future__ import annotations

from collections.abc import Mapping

if __package__:
    from .agent_analysis_runtime import _enabled, _route
    from .agent_runtime_policy import AgentPolicy, PolicyError
    from .agent_task_client import _routed_environment
    from .ai_budget import BudgetDenied, MoneyLedger
    from .ai_guarded_client import GuardedAIClient, GuardError
    from .ai_policy import AnalysisTier
else:
    from agent_analysis_runtime import _enabled, _route
    from agent_runtime_policy import AgentPolicy, PolicyError
    from agent_task_client import _routed_environment
    from ai_budget import BudgetDenied, MoneyLedger
    from ai_guarded_client import GuardedAIClient, GuardError
    from ai_policy import AnalysisTier

TIERS = (AnalysisTier.FAST, AnalysisTier.STANDARD, AnalysisTier.PREMIUM)
# Never serialize exception bodies: they can originate in configuration providers.
PUBLIC_REASONS = frozenset({
    'agent_routing_flag_invalid', 'agent_portfolio_route_invalid',
    'agent_invalid_budget_configuration', 'agent_invalid_cloud_flag',
    'agent_cloud_not_approved', 'local_ai_not_enabled', 'local_ai_unavailable',
    'local_ai_output_limit_exceeded', 'ai_broker_connection_required',
    'ai_broker_binding_unavailable', 'ai_ruble_budget_not_enabled',
    'ai_processing_approval_required', 'ai_processing_region_not_approved',
    'timeweb_ai_key_missing', 'ai_model_identifier_missing_or_invalid',
    'ai_model_price_binding_required', 'ai_prices_missing_stale_or_invalid',
    'ai_token_parameter_required', 'ai_completion_token_budget_required',
    'ai_no_route_with_context_capacity', 'ai_route_invalid_tier',
    'ai_route_catalog_invalid', 'ai_model_catalogue_stale',
})


def _reason(error: Exception) -> str:
    code = str(error)
    return code if code in PUBLIC_REASONS else 'agent_configuration_unavailable'


def route_status(user_id: int, connect, *, environment: Mapping[str, str],
                 client_factory=GuardedAIClient) -> dict:
    """Observe one configuration snapshot without changing the live environment.

    Hybrid flags use the exact validators and per-call environment builder used
    by AnalysisTaskAdapter/AgentTaskClient. An invalid hybrid config never falls
    back to the legacy client's default (potentially paid) route. Existing jobs
    still own their immutable admission receipts; this selection is for NEW jobs.
    """
    if type(user_id) is not int or user_id <= 0:
        raise GuardError('agent_invalid_user')
    if not isinstance(environment, Mapping):
        raise GuardError('agent_configuration_unavailable')
    env = dict(environment)
    routing = {
        'enabled': None, 'control_mode': 'blocked', 'selected_route': None,
        'scope': 'new_portfolio_tasks', 'existing_tasks_use_saved_admission': True,
        'readiness_basis': 'configuration_only', 'inference_verified': False,
        'paid_fallback_enabled': False, 'configuration_reason': None,
        'budget_scope': 'existing_ledger',
    }
    readiness = []
    budget_env = env
    try:
        enabled = _enabled(env)
        routing['enabled'] = enabled
        if enabled:
            mode = _route(env)
            routing.update(control_mode='agent', selected_route=mode,
                           budget_scope='agent_portfolio_requests')
            policy = AgentPolicy.from_environment(env)
            # Show the effective external-call envelope even when the current
            # portfolio route is local. Counts include all existing ledger work.
            budget_env = _routed_environment(env, policy, True)
            if mode == 'timeweb' and (not policy.cloud_enabled or
                    env.get('AI_EXTERNAL_PROCESSING_APPROVED') != 'true'):
                raise GuardError('agent_cloud_not_approved')
            selected = _routed_environment(env, policy, mode == 'timeweb')
        else:
            routing.update(control_mode='legacy', selected_route='legacy',
                           paid_fallback_enabled=None)
            selected = env
        client = client_factory(user_id, connect, env=selected)
        for tier in TIERS:
            try:
                client.check_ready(tier)
                readiness.append({'tier': tier.value, 'ready': True, 'reason': None})
            except (GuardError, BudgetDenied) as error:
                readiness.append({'tier': tier.value, 'ready': False, 'reason': _reason(error)})
    except (GuardError, BudgetDenied, PolicyError) as error:
        code = _reason(error)
        routing['configuration_reason'] = code
        readiness = [{'tier': tier.value, 'ready': False, 'reason': code} for tier in TIERS]
        if isinstance(error, PolicyError) or routing['control_mode'] == 'blocked':
            # Report a closed envelope rather than advertising the old limit
            # when the selected policy itself could not be validated.
            budget_env = {name: '0' for name in (
                'AI_USER_DAILY_RUB', 'AI_PROJECT_DAILY_RUB',
                'AI_USER_MONTHLY_RUB', 'AI_PROJECT_MONTHLY_RUB')}
    configured = len(readiness) == len(TIERS) and all(row['ready'] for row in readiness)
    routing['configuration_ready'] = configured
    spending = MoneyLedger(connect).user_summary(user_id, environ=budget_env)
    # The global ledger's reconciliation flag is distinct from local availability.
    # A ready local socket must not be labelled unavailable because cloud is paused.
    return {'ai_configured': configured, 'route_readiness': readiness,
            'agent_routing': routing, 'spending': spending}
