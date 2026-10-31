"""Local-first Jarvis admission planning; no dispatch, spending or trading.

This is a stage-1 preflight, not a budget reservation or execution authority.
Trusted callers supply fresh ledger/availability/privacy signals. The existing
MoneyLedger and guarded client must revalidate and reserve before any paid call.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .ai_budget import BudgetDenied, MAX_MONEY, SCALE, configured_limits, micro_rub

PLANNED_DAILY_CAP = 95 * SCALE
PLANNED_MONTHLY_CAP = 2000 * SCALE


class PolicyError(ValueError):
    """Fixed error codes only; never expose configuration values or secrets."""


class TaskKind(str, Enum):
    CONVERSATION = 'conversation'
    PUBLIC_RESEARCH = 'public_research'
    PORTFOLIO_REVIEW = 'portfolio_review'
    SYSTEM_STATUS = 'system_status'
    SPEECH_RECOGNITION = 'speech_recognition'
    SPEECH_SYNTHESIS = 'speech_synthesis'


class Target(str, Enum):
    LOCAL_MODEL = 'local_model'
    LOCAL_SERVICE = 'local_service'
    TIMEWEB_PREFLIGHT = 'timeweb_preflight'
    DEFER = 'defer'


LOCAL_SERVICES = frozenset({TaskKind.SYSTEM_STATUS, TaskKind.SPEECH_RECOGNITION,
                            TaskKind.SPEECH_SYNTHESIS})


def _flags(*values: bool) -> None:
    if any(type(value) is not bool for value in values):
        raise PolicyError('agent_invalid_flag')


def _money(*values: int) -> None:
    if any(type(value) is not int or not 0 <= value <= MAX_MONEY for value in values):
        raise PolicyError('agent_invalid_money')


@dataclass(frozen=True)
class AgentPolicy:
    cloud_enabled: bool = False
    daily_cap_micro_rub: int = 0
    monthly_cap_micro_rub: int = 0

    def __post_init__(self) -> None:
        _flags(self.cloud_enabled)
        _money(self.daily_cap_micro_rub, self.monthly_cap_micro_rub)
        if (self.daily_cap_micro_rub > PLANNED_DAILY_CAP or
                self.monthly_cap_micro_rub > PLANNED_MONTHLY_CAP):
            raise PolicyError('agent_cap_above_plan')

    @classmethod
    def from_environment(cls, env: Mapping[str, str]) -> 'AgentPolicy':
        """Read explicit settings without changing the environment or live policy.

        A supplied mapping is required: importing or testing this module never
        discovers production credentials/settings from the process environment.
        The narrower current user/project budgets always win.
        """
        flag = env.get('AGENT_CLOUD_ENABLED', 'false')
        if type(flag) is not str or flag not in {'true', 'false'}:
            raise PolicyError('agent_invalid_cloud_flag')
        try:
            user_day, project_day, user_month, project_month = configured_limits(env)
            day = micro_rub(env.get('AGENT_CLOUD_DAILY_RUB', '95'))
            month = micro_rub(env.get('AGENT_CLOUD_MONTHLY_RUB', '2000'))
        except BudgetDenied:
            raise PolicyError('agent_invalid_budget_configuration') from None
        return cls(flag == 'true', min(user_day, project_day, day, PLANNED_DAILY_CAP),
                   min(user_month, project_month, month, PLANNED_MONTHLY_CAP))


@dataclass(frozen=True)
class TaskRequest:
    kind: TaskKind
    requires_cloud: bool = False
    cloud_data_approved: bool = False
    contains_secrets: bool = False
    requires_fresh_sources: bool = False
    sources_fresh: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, TaskKind):
            raise PolicyError('agent_unknown_task')
        _flags(self.requires_cloud, self.cloud_data_approved, self.contains_secrets,
               self.requires_fresh_sources, self.sources_fresh)
        if self.kind in LOCAL_SERVICES and self.requires_cloud:
            raise PolicyError('agent_service_is_local_only')


@dataclass(frozen=True)
class Availability:
    local_model_ready: bool = False
    local_model_busy: bool = False
    local_service_ready: bool = False
    cloud_route_ready: bool = False

    def __post_init__(self) -> None:
        _flags(self.local_model_ready, self.local_model_busy,
               self.local_service_ready, self.cloud_route_ready)


@dataclass(frozen=True)
class BudgetSnapshot:
    """Conservative committed totals incl. reservations and uncertain charges.

    Each committed total must be at least the relevant user AND project total.
    `current` is a trusted caller assertion. This immutable snapshot cannot
    protect against concurrent dispatch; reservation remains mandatory.
    """
    daily_committed_micro_rub: int = 0
    monthly_committed_micro_rub: int = 0
    quoted_ceiling_micro_rub: int | None = None
    current: bool = False

    def __post_init__(self) -> None:
        _money(self.daily_committed_micro_rub, self.monthly_committed_micro_rub)
        if self.quoted_ceiling_micro_rub is not None:
            _money(self.quoted_ceiling_micro_rub)
        _flags(self.current)


@dataclass(frozen=True)
class TaskPlan:
    target: Target
    reason: str

    @property
    def requires_atomic_reservation(self) -> bool:
        return self.target is Target.TIMEWEB_PREFLIGHT

    @property
    def authorizes_trade(self) -> bool:
        return False


def _defer(reason: str) -> TaskPlan:
    return TaskPlan(Target.DEFER, reason)


def plan_task(request: TaskRequest, policy: AgentPolicy, availability: Availability,
              budget: BudgetSnapshot | None = None) -> TaskPlan:
    """Choose an admission plan without invoking any model, network or broker.

    Local outages/busy states do not cause paid fallback. Cloud-required work
    never silently downgrades to a local financial review. Freshness and privacy
    checks apply before either model is considered.
    """
    if request.contains_secrets:
        return _defer('secret_input_blocked')
    if (request.kind is TaskKind.PORTFOLIO_REVIEW or request.requires_fresh_sources) and not request.sources_fresh:
        return _defer('fresh_sources_required')
    if request.kind in LOCAL_SERVICES:
        if availability.local_service_ready:
            return TaskPlan(Target.LOCAL_SERVICE, 'local_service_only')
        return _defer('local_service_unavailable')
    if not request.requires_cloud:
        if not availability.local_model_ready:
            return _defer('local_model_unavailable')
        if availability.local_model_busy:
            return _defer('local_model_busy')
        return TaskPlan(Target.LOCAL_MODEL, 'local_first')
    if not policy.cloud_enabled:
        return _defer('cloud_disabled')
    if not request.cloud_data_approved:
        return _defer('cloud_data_not_approved')
    if not availability.cloud_route_ready:
        return _defer('cloud_route_unavailable')
    if policy.daily_cap_micro_rub == 0 or policy.monthly_cap_micro_rub == 0:
        return _defer('cloud_budget_disabled')
    if budget is None or not budget.current:
        return _defer('fresh_budget_required')
    cost = budget.quoted_ceiling_micro_rub
    if cost is None or cost == 0:
        return _defer('paid_quote_required')
    if cost + budget.daily_committed_micro_rub > policy.daily_cap_micro_rub:
        return _defer('daily_budget_exhausted')
    if cost + budget.monthly_committed_micro_rub > policy.monthly_cap_micro_rub:
        return _defer('monthly_budget_exhausted')
    return TaskPlan(Target.TIMEWEB_PREFLIGHT, 'atomic_reservation_required')
