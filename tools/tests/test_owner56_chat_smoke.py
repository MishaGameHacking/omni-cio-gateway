import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location("smoke", Path(__file__).parents[1] / "owner56_chat_smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class ChatSmokeTests(unittest.TestCase):
    def api(self):
        api = Mock()
        api.estimate.return_value = {"available": True, "cost_ceiling_micro_rub": 1_781_820,
                                     "selected_tier": "fast", "requires_cost_confirmation": False}
        api.thread.return_value = "synthetic-thread"
        api.send.return_value = "synthetic-job"
        api.state.return_value = "completed"
        api.messages.return_value = [
            {"request_id": "synthetic-request", "role": "user", "text": "synthetic question"},
            {"request_id": "synthetic-request", "role": "assistant", "text": "synthetic answer"}]
        return api

    def test_refuses_unavailable_excessive_or_deep_quote_before_creating_thread(self):
        for override in ({"available": False}, {"cost_ceiling_micro_rub": 2_000_001},
                         {"cost_ceiling_micro_rub": True}, {"cost_ceiling_micro_rub": 0},
                         {"selected_tier": "premium"}, {"requires_cost_confirmation": True}):
            with self.subTest(override=override):
                api = self.api()
                api.estimate.return_value.update(override)
                self.assertEqual(smoke.verify(api, "synthetic-request")["status"], "blocked")
                api.thread.assert_not_called()
                api.send.assert_not_called()

    def test_rechecks_quote_with_actual_thread_before_send(self):
        api = self.api()
        api.estimate.side_effect = [api.estimate.return_value, {"available": False}]
        self.assertEqual(smoke.verify(api, "synthetic-request")["status"], "blocked")
        api.send.assert_not_called()

    def test_only_exactly_one_completed_answer_verifies(self):
        api = self.api()
        result = smoke.verify(api, "synthetic-request")
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["answer_present"])
        api.send.assert_called_once_with("synthetic-thread", smoke.QUESTION, "synthetic-request", api.estimate.return_value)
        self.assertNotIn("synthetic answer", str(result))

    def test_no_answer_failed_job_or_duplicate_answer_never_verifies(self):
        for state, rows in (("failed", []), ("running", []), ("completed", [])):
            api = self.api()
            api.state.return_value, api.messages.return_value = state, rows
            self.assertEqual(smoke.verify(api, "synthetic-request")["status"], "incomplete")
        api = self.api()
        api.messages.return_value.append(api.messages.return_value[-1])
        self.assertEqual(smoke.verify(api, "synthetic-request")["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
