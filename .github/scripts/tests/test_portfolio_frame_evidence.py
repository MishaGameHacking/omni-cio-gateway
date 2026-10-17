"""Adversarial transcript parsing only; these tests do not run Android screens."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portfolio_frame_evidence import has_call, portfolio_observation

RUN_ID = "a" * 32


def observe(root, route="history", scenario="ready"):
    return portfolio_observation(root, route, scenario, RUN_ID)


def frame(route="history", scenario="ready", *, requests="1", errors="0", package="ru.omnicio.app.debug"):
    transcript = {"route": route, "scenario": scenario,
                  "calls": [{"sequence": 1, "method": "GET", "path": "/portfolio/history",
                             "parameters": {"account_id": "synthetic-account", "currency": "RUB", "resolution": "hour"},
                             "status": 200}],
                  "contract_errors": 0, "destination": {"section": 2, "account_id": "synthetic-account"},
                  "opened_sources": [], "initialized": True, "run_id": RUN_ID, "current_page": "history", "request_count": 1}
    root = ET.Element("hierarchy")
    for resource, description in (("portfolio-probe", f"portfolio-probe:{route}/{scenario};transport:synthetic;initialized:true;requests:{requests};contract-errors:{errors};page:history;run:{RUN_ID}"),
                                  ("portfolio-probe-transcript", json.dumps(transcript))):
        ET.SubElement(root, "node", {"package": package, "visible-to-user": "true", "bounds": "[0,0][2,2]",
                                     "resource-id": resource, "content-desc": description})
    return root


def replace_transcript(root, change):
    node = list(root)[1]
    value = json.loads(node.get("content-desc"))
    change(value)
    node.set("content-desc", json.dumps(value))


class PortfolioFrameEvidenceTests(unittest.TestCase):
    def test_exact_visible_identity_and_native_source_call_are_required(self):
        observed = observe(frame())
        self.assertEqual(1, observed["requests"])
        params = {"account_id": "synthetic-account", "currency": "RUB", "resolution": "hour"}
        self.assertTrue(has_call(observed, "/portfolio/history", params))
        for path, values, status, after in (("/portfolio/history-other", params, 200, 0),
                                             ("/portfolio/history", {**params, "resolution": "day"}, 200, 0),
                                             ("/portfolio/history", params, 503, 0),
                                             ("/portfolio/history", params, 200, 1)):
            self.assertFalse(has_call(observed, path, values, status=status, after=after))
        for root in (frame(package="another.app"), frame(scenario="partial"), frame(requests="2")):
            self.assertIsNone(observe(root))

    def test_hidden_wrong_window_or_missing_transcript_is_not_evidence(self):
        for index in (0, 1):
            root = frame()
            root[index].set("visible-to-user", "false")
            self.assertIsNone(observe(root))
            root = frame()
            root[index].set("bounds", "[0,0][0,0]")
            self.assertIsNone(observe(root))
        root = frame()
        root.remove(root[1])
        self.assertIsNone(observe(root))

    def test_invalid_contract_duplicate_json_fields_and_coerced_status_fail_closed(self):
        for change in (lambda value: value.update(contract_errors=1),
                       lambda value: value.update(contract_errors=True),
                       lambda value: value["calls"][0].update(sequence=2),
                       lambda value: value["calls"][0].update(sequence=True),
                       lambda value: value["calls"][0].update(status="200"),
                       lambda value: value["calls"][0].update(parameters={"offset": True}),
                       lambda value: value["calls"][0].update(path=None)):
            root = frame()
            replace_transcript(root, change)
            with self.assertRaises(AssertionError):
                observe(root)
        root = frame()
        raw = root[1].get("content-desc")
        root[1].set("content-desc", raw[:-1] + ', "contract_errors": 1}')
        with self.assertRaises(AssertionError):
            observe(root)
        with self.assertRaises(AssertionError):
            observe(frame(errors="1"))

    def test_initial_screen_without_source_calls_is_ready_but_has_no_endpoint_evidence(self):
        for route in ("appearance", "history", "dossier", "quotes"):
            root = frame(route=route, requests="0")
            replace_transcript(root, lambda value: value.update(calls=[], request_count=0))
            result = observe(root, route)
            self.assertEqual([], result["calls"])
            self.assertFalse(has_call(result, "/portfolio/history", {}))

    def test_wrong_run_or_uninitialized_saved_profile_cannot_pass_readiness(self):
        for change in (lambda value: value.update(run_id="b" * 32),
                       lambda value: value.update(initialized=False),
                       lambda value: value.update(initialized=1)):
            root = frame()
            replace_transcript(root, change)
            self.assertIsNone(observe(root))
        for old, new in (("run:" + RUN_ID, "run:" + "b" * 32), ("initialized:true", "initialized:false"),
                         ("page:history", "page:discovery")):
            root = frame()
            root[0].set("content-desc", root[0].get("content-desc").replace(old, new))
            self.assertIsNone(observe(root))

    def test_conflicting_visible_transcripts_are_not_arbitrarily_selected(self):
        root = frame()
        duplicate = deepcopy(root[1])
        changed = json.loads(duplicate.get("content-desc"))
        changed["destination"] = {"instrument_uid": "another-position"}
        duplicate.set("content-desc", json.dumps(changed))
        root.append(duplicate)
        self.assertIsNone(observe(root))


if __name__ == "__main__":
    unittest.main()
