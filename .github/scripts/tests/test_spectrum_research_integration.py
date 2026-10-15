"""Source wiring invariants, not visual or installation tests.

The native redesign moves the single research panel from Recommendations to
Risks. It must remain independently reachable even when the ideas API fails.
Behavioral research/update integration tests remain in backend/tests.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
NATIVE = ROOT / 'app/src/main/java/ru/omnicio/app'
DEBUG = ROOT / 'app/src/debug/java/ru/omnicio/app'


class SpectrumResearchIntegrationTests(unittest.TestCase):
    def source(self, relative):
        return (NATIVE / relative).read_text(encoding='utf-8')

    def test_research_panel_is_single_and_independent_of_ideas_response(self):
        source = self.source('ui/analysis/AnalysisScreens.kt')
        start = source.index('private fun IdeasContent(')
        end = source.index('fun AnalysisProfileSettingsScreen(', start)
        ideas = source[start:end]
        self.assertIn('item(key = "portfolio-research")', ideas)
        self.assertIn('navigate(AnalystTab.Risks)', ideas)
        self.assertLess(ideas.index('navigate(AnalystTab.Risks)'), ideas.index('state.value?.let'))
        risks = self.source('ui/home/MarketAndRiskScreens.kt')
        risks = risks[risks.index('fun RisksScreen('):risks.index('private fun RiskOverview(')]
        self.assertEqual(risks.count('PortfolioResearchPanel(accessToken)'), 1)
        self.assertIn('item(key = "risk-research")', risks)
        self.assertNotIn('state.value', risks)
        self.assertNotIn('IdeasState', risks)
        all_screens = list((NATIVE / 'ui').rglob('*.kt'))
        calls = sum(path.read_text(encoding='utf-8').count('PortfolioResearchPanel(') for path in all_screens)
        self.assertEqual(calls, 2, 'one declaration and one independently mounted panel')
        main = self.source('MainActivity.kt')
        self.assertIn('AppScreen.Risks -> RisksScreen(', main)
        self.assertIn('AnalystTab.Risks -> AppScreen.Risks', main)
        self.assertIn('AnalystTab.Risks', self.source('ui/home/HomeScreen.kt'))

    def test_research_client_joins_existing_version_gate(self):
        source = self.source('data/research/ResearchClient.kt')
        for required in ('ClientVersion.attach(this)', 'ClientVersion.observeStatus(status)',
                         '426 -> BackendResult.Failure', 'instanceFollowRedirects = false'):
            self.assertIn(required, source)
        self.assertIn('/analysis/research', source)

    def test_research_does_not_add_nested_vertical_scroll(self):
        source = self.source('ui/research/PortfolioResearchPanel.kt')
        self.assertNotIn('LazyColumn(', source)
        self.assertNotIn('.verticalScroll(', source)
        self.assertIn('researchPage(', source)
        self.assertIn('validSnapshot(', source)

    def test_both_research_and_spectrum_checks_execute_in_debug_probe(self):
        fixture = (DEBUG / 'ProfileUiProbeActivity.kt').read_text(encoding='utf-8')
        for required in ('runInstrumentLinkRegressions()', 'runResearchPresentationChecks()',
                         'runEducationCatalogChecks()', 'runUpdatePolicyChecks()',
                         'runPortfolioGeometryChecks()', 'runInstrumentDetailsChecks()',
                         'runPositionSelectionChecks()', 'runRefreshStateRegressionChecks()',
                         'probe-research-presentation-tests:', 'probe-education-tests:'):
            with self.subTest(required=required):
                self.assertIn(required, fixture)

    def test_actual_app_registers_both_router_and_update_routes(self):
        module = ast.parse((ROOT / 'backend/app.py').read_text(encoding='utf-8'))
        calls = [item for item in ast.walk(module) if isinstance(item, ast.Call)]
        routers = [call for call in calls if isinstance(call.func, ast.Attribute)
                   and isinstance(call.func.value, ast.Name) and call.func.value.id == 'app'
                   and call.func.attr == 'include_router' and call.args
                   and isinstance(call.args[0], ast.Name)]
        self.assertEqual(sum(call.args[0].id == 'portfolio_research_router' for call in routers), 1)
        update_calls = [call for call in calls if isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == 'client_updates' and call.func.attr == 'install_routes']
        self.assertEqual(len(update_calls), 1)
        self.assertEqual([arg.id for arg in update_calls[0].args if isinstance(arg, ast.Name)],
                         ['app', 'connect', 'session_user'])

    def test_release_publication_is_explicit_even_when_artifact_storage_is_full(self):
        workflow = (ROOT / '.github/workflows/android-apk.yml').read_text(encoding='utf-8')
        publication = workflow[workflow.index('- name: Publish verified APK to GitHub Releases'):]
        self.assertIn("github.ref == 'refs/heads/main'", publication)
        self.assertIn("github.event_name == 'workflow_dispatch'", publication)
        self.assertIn("github.event_name == 'push'", publication)
        self.assertIn("contains(github.event.head_commit.message, '[publish-apk]')", publication)
        self.assertIn('uses: ./.github/actions/check-apk', workflow)
        self.assertNotIn('publish_moscow_release.sh', workflow)
        self.assertIn('report.version_code <= 22', publication)


if __name__ == '__main__':
    unittest.main()
