"""Synthetic, offline checks: no real model, cloud, microphone or broker."""
from dataclasses import replace
import unittest

from backend.ai_budget import SCALE
from backend.agent_runtime_policy import (
    AgentPolicy, Availability, BudgetSnapshot, LOCAL_SERVICES, PolicyError,
    Target, TaskKind, TaskRequest, plan_task,
)


class AgentRuntimePolicyTests(unittest.TestCase):
    def setUp(self):
        self.env = {'AGENT_CLOUD_ENABLED': 'true', 'AI_USER_DAILY_RUB': '95',
                    'AI_PROJECT_DAILY_RUB': '95', 'AI_USER_MONTHLY_RUB': '2900',
                    'AI_PROJECT_MONTHLY_RUB': '2900'}
        self.policy = AgentPolicy.from_environment(self.env)
        self.ready = Availability(True, False, True, True)
        self.local = TaskRequest(TaskKind.CONVERSATION)
        self.cloud = TaskRequest(TaskKind.CONVERSATION, requires_cloud=True,
                                 cloud_data_approved=True)
        self.budget = BudgetSnapshot(0, 0, SCALE, True)

    def plan(self, request=None, policy=None, availability=None, budget=None):
        return plan_task(request or self.local, policy or self.policy,
                         availability or self.ready, budget)

    def test_missing_settings_disable_paid_work(self):
        policy = AgentPolicy.from_environment({})
        self.assertFalse(policy.cloud_enabled)
        self.assertEqual(policy.daily_cap_micro_rub, 0)

    def test_new_plan_does_not_rewrite_existing_settings(self):
        before = dict(self.env)
        self.assertEqual(self.policy.monthly_cap_micro_rub, 2000 * SCALE)
        self.assertEqual(self.env, before)

    def test_lower_existing_caps_win(self):
        env = dict(self.env, AI_USER_DAILY_RUB='20', AI_PROJECT_DAILY_RUB='10',
                   AI_USER_MONTHLY_RUB='600', AI_PROJECT_MONTHLY_RUB='300')
        policy = AgentPolicy.from_environment(env)
        self.assertEqual((policy.daily_cap_micro_rub, policy.monthly_cap_micro_rub),
                         (10 * SCALE, 300 * SCALE))

    def test_agent_settings_can_only_lower_plan(self):
        policy = AgentPolicy.from_environment(dict(self.env, AGENT_CLOUD_DAILY_RUB='500',
                                                   AGENT_CLOUD_MONTHLY_RUB='9000'))
        self.assertEqual((policy.daily_cap_micro_rub, policy.monthly_cap_micro_rub),
                         (95 * SCALE, 2000 * SCALE))
        lower = AgentPolicy.from_environment(dict(self.env, AGENT_CLOUD_DAILY_RUB='5',
                                                  AGENT_CLOUD_MONTHLY_RUB='50'))
        self.assertEqual((lower.daily_cap_micro_rub, lower.monthly_cap_micro_rub),
                         (5 * SCALE, 50 * SCALE))

    def test_invalid_cloud_flag_fails_closed(self):
        for value in ('yes', '1', '', True, None):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                AgentPolicy.from_environment(dict(self.env, AGENT_CLOUD_ENABLED=value))

    def test_invalid_budget_configuration_fails_closed(self):
        for value in ('NaN', 'Infinity', '-1', 'secret-invalid-value'):
            with self.subTest(value=value), self.assertRaisesRegex(PolicyError, '^agent_invalid_budget_configuration$'):
                AgentPolicy.from_environment(dict(self.env, AGENT_CLOUD_MONTHLY_RUB=value))

    def test_invalid_money_types_rejected(self):
        for value in (True, -1, 1.5, '1'):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                BudgetSnapshot(quoted_ceiling_micro_rub=value)

    def test_policy_cannot_bypass_ceiling(self):
        with self.assertRaises(PolicyError):
            AgentPolicy(True, 96 * SCALE, 2000 * SCALE)
        with self.assertRaises(PolicyError):
            AgentPolicy(True, 95 * SCALE, 2001 * SCALE)

    def test_unknown_task_rejected(self):
        for value in ('conversation', 'execute_trade', 'run_shell'):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                TaskRequest(value)

    def test_truthy_strings_are_not_permissions(self):
        with self.assertRaises(PolicyError):
            TaskRequest(TaskKind.CONVERSATION, cloud_data_approved='true')
        with self.assertRaises(PolicyError):
            Availability(cloud_route_ready='true')

    def test_routine_work_uses_local_model_even_when_cloud_ready(self):
        decision = self.plan(budget=self.budget)
        self.assertEqual(decision.target, Target.LOCAL_MODEL)
        self.assertFalse(decision.requires_atomic_reservation)

    def test_cloud_disabled_does_not_stop_local_work(self):
        self.assertEqual(self.plan(policy=AgentPolicy()).target, Target.LOCAL_MODEL)

    def test_exhausted_cloud_budget_does_not_stop_local_work(self):
        spent = BudgetSnapshot(100 * SCALE, 3000 * SCALE, SCALE, True)
        self.assertEqual(self.plan(budget=spent).target, Target.LOCAL_MODEL)

    def test_local_outage_never_escalates_to_paid_model(self):
        result = self.plan(availability=replace(self.ready, local_model_ready=False), budget=self.budget)
        self.assertEqual((result.target, result.reason), (Target.DEFER, 'local_model_unavailable'))

    def test_local_busy_never_escalates_to_paid_model(self):
        result = self.plan(availability=replace(self.ready, local_model_busy=True), budget=self.budget)
        self.assertEqual(result.reason, 'local_model_busy')

    def test_local_services_do_not_need_language_model(self):
        for kind in LOCAL_SERVICES:
            with self.subTest(kind=kind):
                result = self.plan(TaskRequest(kind), availability=Availability(local_service_ready=True))
                self.assertEqual(result.target, Target.LOCAL_SERVICE)

    def test_unavailable_local_service_defers(self):
        result = self.plan(TaskRequest(TaskKind.SPEECH_SYNTHESIS), availability=Availability())
        self.assertEqual(result.reason, 'local_service_unavailable')

    def test_stage_one_never_routes_audio_or_system_status_to_cloud(self):
        for kind in LOCAL_SERVICES:
            with self.subTest(kind=kind), self.assertRaises(PolicyError):
                TaskRequest(kind, requires_cloud=True)

    def test_secrets_blocked_for_local_and_cloud(self):
        for request in (self.local, self.cloud):
            with self.subTest(cloud=request.requires_cloud):
                self.assertEqual(self.plan(replace(request, contains_secrets=True), budget=self.budget).reason,
                                 'secret_input_blocked')

    def test_portfolio_review_always_requires_fresh_sources(self):
        for cloud in (False, True):
            request = TaskRequest(TaskKind.PORTFOLIO_REVIEW, requires_cloud=cloud, cloud_data_approved=True)
            with self.subTest(cloud=cloud):
                self.assertEqual(self.plan(request, budget=self.budget).reason, 'fresh_sources_required')

    def test_fresh_portfolio_can_use_local_model(self):
        request = TaskRequest(TaskKind.PORTFOLIO_REVIEW, sources_fresh=True)
        self.assertEqual(self.plan(request).target, Target.LOCAL_MODEL)

    def test_research_freshness_requirement_is_preserved(self):
        request = TaskRequest(TaskKind.PUBLIC_RESEARCH, requires_fresh_sources=True)
        self.assertEqual(self.plan(request).reason, 'fresh_sources_required')

    def test_cloud_requires_explicit_enablement(self):
        self.assertEqual(self.plan(self.cloud, policy=AgentPolicy(), budget=self.budget).reason,
                         'cloud_disabled')

    def test_cloud_requires_data_approval(self):
        self.assertEqual(self.plan(replace(self.cloud, cloud_data_approved=False), budget=self.budget).reason,
                         'cloud_data_not_approved')

    def test_cloud_outage_does_not_downgrade_required_review(self):
        result = self.plan(self.cloud, availability=replace(self.ready, cloud_route_ready=False), budget=self.budget)
        self.assertEqual((result.target, result.reason), (Target.DEFER, 'cloud_route_unavailable'))

    def test_zero_budget_disables_paid_work(self):
        for policy in (AgentPolicy(True, 0, SCALE), AgentPolicy(True, SCALE, 0)):
            with self.subTest(policy=policy):
                self.assertEqual(self.plan(self.cloud, policy=policy, budget=self.budget).reason,
                                 'cloud_budget_disabled')

    def test_missing_or_stale_budget_is_not_admitted(self):
        for budget in (None, replace(self.budget, current=False)):
            with self.subTest(budget=budget):
                self.assertEqual(self.plan(self.cloud, budget=budget).reason, 'fresh_budget_required')

    def test_missing_or_zero_paid_quote_is_not_admitted(self):
        for value in (None, 0):
            with self.subTest(value=value):
                result = self.plan(self.cloud, budget=replace(self.budget, quoted_ceiling_micro_rub=value))
                self.assertEqual(result.reason, 'paid_quote_required')

    def test_daily_committed_includes_reservations(self):
        budget = replace(self.budget, daily_committed_micro_rub=95 * SCALE)
        self.assertEqual(self.plan(self.cloud, budget=budget).reason, 'daily_budget_exhausted')

    def test_monthly_committed_includes_uncertain_requests(self):
        budget = replace(self.budget, monthly_committed_micro_rub=2000 * SCALE)
        self.assertEqual(self.plan(self.cloud, budget=budget).reason, 'monthly_budget_exhausted')

    def test_exact_remaining_budget_requires_atomic_reservation(self):
        budget = BudgetSnapshot(94 * SCALE, 1999 * SCALE, SCALE, True)
        result = self.plan(self.cloud, budget=budget)
        self.assertEqual(result.target, Target.TIMEWEB_PREFLIGHT)
        self.assertTrue(result.requires_atomic_reservation)
        self.assertEqual(result.reason, 'atomic_reservation_required')

    def test_no_plan_authorizes_a_trade(self):
        cases = (self.plan(), self.plan(self.cloud, budget=self.budget),
                 self.plan(TaskRequest(TaskKind.SYSTEM_STATUS)),
                 self.plan(availability=Availability()))
        self.assertEqual({case.target for case in cases}, set(Target))
        self.assertTrue(all(not case.authorizes_trade for case in cases))


if __name__ == '__main__':
    unittest.main()
