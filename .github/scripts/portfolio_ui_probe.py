"""Bounded production portfolio flows on the disposable Android emulator.

Every request uses the debug-only synthetic read transport. The production
widgets, navigation, native input and mesh renderer are exercised unchanged.
"""
from __future__ import annotations

from datetime import date, datetime
import json
import math
from pathlib import Path
import re
import secrets
import time

from business_ui_probe import BANNER, labels
from portfolio_frame_evidence import has_call, portfolio_observation
from profile_launch import PACKAGE, PORTFOLIO_CASES, launch_profile
from profile_ui_probe import node_bounds

CASES = PORTFOLIO_CASES


class PortfolioCase:
    def __init__(self, probe, route, scenario, font_scale, run_id):
        self.probe, self.route, self.scenario = probe, route, scenario
        self.font_scale, self.run_id = font_scale, run_id
        self.screenshots = []
        self.extra = {}
        self.before = self.observed()
        self.day = date.fromisoformat(self.before["day"])
        self.history_start = date.fromisoformat(self.before["history_start"])
        self.history_end = date.fromisoformat(self.before["history_end"])
        self.history_instant = datetime.fromisoformat(self.before["history_instant"].replace("Z", "+00:00"))
        if not self.history_start <= self.history_instant.date() <= self.history_end < self.day:
            raise AssertionError("Synthetic source history boundaries are inconsistent")

    def _read(self):
        return portfolio_observation(self.probe.tree(), self.route, self.scenario, self.run_id)

    def observed(self):
        return self.probe.wait_for(self._read, "Portfolio fixture did not expose its initialized exact source transcript")

    def expect(self, predicate, message):
        def read():
            observed = self._read()
            return observed if observed is not None and predicate(observed) else None
        return self.probe.wait_for(read, message)

    def call(self, path, parameters, *, status=200, after=0):
        return self.expect(lambda value: has_call(value, path, parameters, status=status, after=after),
                           "Production screen did not complete the exact source contract: " + path)

    def capture(self, stage=None):
        name = "portfolio-" + self.route + "-" + (stage or self.scenario)
        if math.isclose(self.font_scale, 2.0):
            name += "-font-200"
        self.probe.capture(name)
        self.screenshots.append(name + ".png")
        return name

    def launch(self):
        launch_profile(self.probe.command, self.probe.tree, self.probe.wait_for,
                       expected_screen="portfolio-" + self.route, scenario=self.scenario, run_id=self.run_id)
        return self.observed()

    def prefix(self, text, *, area="workspace-content", direction="end"):
        reader = getattr(self.probe.read_tree, "__self__", None)
        for _ in range(21):
            tree = self.probe.tree()
            for node in tree.iter("node"):
                if node.get("package") == PACKAGE and node.get("visible-to-user") != "false" \
                        and any(label.startswith(text) for label in labels(node)):
                    node_bounds(node)
                    return node
            if not reader.scroll_list(area, direction):
                break
            time.sleep(.15)
        raise AssertionError("Expected native portfolio text is not visible: " + text)

    def search(self, text):
        from native_input_evidence import focused_editor
        if re.fullmatch(r"[A-Za-z0-9_-]{0,40}", text) is None:
            raise ValueError("Only bounded synthetic ASCII search terms belong to this fixture")
        self.probe.tap_visible("Поиск по приложению")
        # Public Android input keycombination sends actual Ctrl+A / Delete to
        # the focused native editor; no fixture state setter is called.
        self.probe.command("shell", "input", "keycombination", "113", "29")
        self.probe.command("shell", "input", "keyevent", "KEYCODE_DEL")
        if text:
            self.probe.command("shell", "input", "text", text)
        self.probe.wait_for(lambda: focused_editor(self.probe.tree(), text), "Search did not enter the actual native editor")
        self.probe.command("shell", "input", "keyevent", "BACK")

    def record_text(self, resource_id, text, *, direction="end"):
        """Bind a value to its exact native source record even at 200% font."""
        self.probe.reveal_resource(resource_id, "workspace-content", direction=direction)
        reader = getattr(self.probe.read_tree, "__self__", None)
        for _ in range(21):
            tree = self.probe.tree()
            records = [node for node in tree.iter("node") if node.get("package") == PACKAGE
                       and node.get("visible-to-user") == "true"
                       and node.get("resource-id") in {resource_id, PACKAGE + ":id/" + resource_id}]
            if len(records) > 1:
                raise AssertionError("A source-record tag identifies several native records")
            for record in records:
                for node in record.iter("node"):
                    if node.get("package") == PACKAGE and node.get("visible-to-user") == "true" and text in labels(node):
                        node_bounds(node)
                        return node
            if not reader.scroll_list("workspace-content", direction):
                break
            time.sleep(.15)
        raise AssertionError("Exact native source record did not expose its value: " + resource_id + " / " + text)

    def destination(self, *, account, query, section=1):
        expected = {"section": section, "account_id": account, "query": query,
                    "sector": None, "kind": None, "operation_id": None, "operation_date": None}
        return self.expect(lambda value: value["current_page"] == "portfolio" and value["destination"] == expected,
                           "Navigation lost the exact account, position or destination section")


def exercise_portfolio(probe):
    from persistent_ui import FrameReader
    from portfolio_research_probe import exercise_discovery, exercise_dossier
    from portfolio_chart_probe import exercise_history, exercise_quotes
    from portfolio_market_probe import exercise_markets
    from portfolio_preferences_probe import exercise_appearance
    from spatial_frame_evidence import ready_spatial_metrics

    reader = getattr(probe.read_tree, "__self__", None)
    if not isinstance(reader, FrameReader):
        raise ValueError("Portfolio acceptance requires the owned persistent native frame session")
    handlers = {"discovery": exercise_discovery, "dossier": exercise_dossier, "history": exercise_history,
                "quotes": exercise_quotes, "markets": exercise_markets, "appearance": exercise_appearance}
    records = []
    for font_scale, (route, scenario) in ((scale, case) for scale in (1.0, 2.0) for case in CASES):
        run_id = secrets.token_hex(16)
        probe.command("shell", "settings", "put", "system", "font_scale", str(font_scale))
        print(f"PORTFOLIO_UI_CASE={route}/{scenario};font={font_scale};run={run_id}", flush=True)
        launch_profile(probe.command, probe.tree, probe.wait_for,
                       expected_screen="portfolio-" + route, scenario=scenario, run_id=run_id)
        probe.find(BANNER)
        case = PortfolioCase(probe, route, scenario, font_scale, run_id)
        checks = handlers[route](case)
        after = case.observed()
        renderer = probe.wait_for(lambda: ready_spatial_metrics(probe.tree()), "Production portfolio screen did not render its genuine meshes")
        if not math.isclose(renderer.get("font-scale", 0.0), font_scale, rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError("Actual native font scale differs from the portfolio acceptance scenario")
        if not checks or len(checks) != len(set(checks)):
            raise AssertionError("Portfolio acceptance did not complete its distinct production actions")
        case.capture()
        records.append({"case": route + "/" + scenario, "font_scale": font_scale, "run_id": run_id,
                        "before": case.before, "after": after, "checks": checks,
                        "renderer": renderer, "screenshots": case.screenshots, "observations": case.extra})
        print(f"PORTFOLIO_UI_CASE_PASSED={route}/{scenario};font={font_scale}", flush=True)
    report = {"fixture": "debug-only-synthetic-read-transports", "actual_device_observations": True,
              "production_destination_screens_exercised": True, "real_broker_or_model_called": False,
              "physical_device_verified": False, "cases": records}
    _write_report(report)
    return report


def _write_report(report):
    base = Path(__file__).resolve().parents[2]
    folder = base / "app/build/outputs/apk/preview/ui-screens"
    destination = folder / "portfolio-verification.json"
    if folder.is_symlink() or not folder.resolve().is_relative_to(base) or destination.is_symlink():
        raise AssertionError("Portfolio evidence escapes checkout")
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if len(payload.encode("utf-8")) > 2 * 1024 * 1024:
        raise AssertionError("Portfolio evidence exceeded the bounded collector")
    destination.write_text(payload, encoding="utf-8")
    print("PORTFOLIO_UI_VERIFICATION=" + json.dumps(report, ensure_ascii=True, sort_keys=True), flush=True)
