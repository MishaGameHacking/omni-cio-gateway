"""Guard compact dashboard wiring; emulator captures remain the rendering gate."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
HOME = ROOT / "app/src/main/java/ru/omnicio/app/ui/home"
PROFILE = ROOT / "app/src/main/java/ru/omnicio/app/ui/profile/ProfileSectionTabs.kt"


class CompactHomeTests(unittest.TestCase):

    def test_real_portfolio_precedes_analysis_without_hiding_blockers(self):
        source = (HOME / "HomeScreen.kt").read_text(encoding="utf-8")
        home = source.split('fun HomeScreen(', 1)[1].split('\nprivate fun automationStateTitle', 1)[0]
        order = re.findall(r'item\(key = "([\w-]+)"\)', home)
        self.assertEqual(order[:4], ["system-header", "portfolio-overview", "portfolio-actions", "automation-state"])
        self.assertLess(order.index("automation-state"), order.index("automation-blockers"))
        self.assertEqual(order, ["system-header", "portfolio-overview", "portfolio-actions", "automation-state", "automation-blockers"])
        for removed in ("analysis-results", "system-connections"):
            self.assertNotIn(removed, order)
        self.assertIn('Text("Главная"', home)
        self.assertIn('status?.records("blockers")', home)
        self.assertIn('discovery?.records("candidates")', home)
        self.assertRegex(home, r'SpectrumTextButton\("Открыть решения", onOpenRecommendations,\s*Modifier.fillMaxWidth\(\)')
        self.assertIn('if (blockers.isNotEmpty())', home)
        self.assertIn('if (disconnected) onConnect else onOpenProfile', home)
        for forbidden in ('portfolio-hero', 'snapshot.totalValue', 'snapshot.allocations',
                          'InteractiveBalance(', 'HoldToRevealBalance(', 'SpectrumMetricPill',
                          'normalizedDashboardOrder', 'saveDashboardOrder'):
            self.assertNotIn(forbidden, home)
        self.assertNotIn("heightIn(max = 150.dp)", home)

    def test_home_reads_saved_server_status_and_keeps_freshness_explicit(self):
        source = (HOME / "HomeScreen.kt").read_text(encoding="utf-8")
        home = source.split('fun HomeScreen(', 1)[1].split('\nprivate fun automationStateTitle', 1)[0]
        self.assertIn('rememberWorkspaceResource("/automation/status")', home)
        self.assertIn('resource.data?.takeIf { it.optInt("schema_version") == 1 }', home)
        self.assertIn('val foreground = workspaceForeground()', home)
        self.assertIn('LaunchedEffect(foreground)', home)
        self.assertIn('if (foreground) while (isActive)', home)
        self.assertIn('status?.text("last_observation_at", "")', home)
        self.assertIn('if (hasObservation) Text("Проверка · " + localMoment(observation)', home)
        self.assertIn('HomeAutomationCard(status, resource.error, resource.busy, resource.refresh', home)
        self.assertIn('val currentError = error', home)
        self.assertIn('Сохранённые сведения могут быть устаревшими.', home)
        for forbidden in ('rememberWorkspaceAction(', '/analysis/refresh', '/workspace/refresh',
                          'System.currentTimeMillis()', 'Instant.now()'):
            self.assertNotIn(forbidden, home)
        data = (ROOT / 'app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceData.kt').read_text(encoding='utf-8')
        read = data.split('fun rememberWorkspaceResource(', 1)[1].split('\n@Composable\nfun workspaceForeground', 1)[0]
        self.assertIn('client.request(session.token, path)', read)
        transport = (ROOT / 'app/src/main/java/ru/omnicio/app/data/workspace/WorkspaceTransport.kt').read_text(encoding='utf-8')
        self.assertIn('method: String = "GET"', transport)

    def test_workspace_shortcuts_keep_real_navigation_callbacks(self):
        source = (HOME / "HomeQuickActions.kt").read_text(encoding="utf-8")
        for callback in ("onAssets", "onPayments"):
            self.assertIn(callback, source)
        self.assertNotIn("SpectrumLiveFeatureIcon(", source)
        self.assertIn("fontScale >= 1.4f", source)
        self.assertIn("widthDp < 260f", source)
        self.assertIn("else 2", source)

    def test_profile_semantics_preserve_full_cell_state_and_activation(self):
        source = PROFILE.read_text(encoding="utf-8")
        self.assertIn("coerceAtLeast(52.dp)", source)
        self.assertIn(".clearAndSetSemantics", source)
        self.assertIn("contentDescription = label", source)
        self.assertIn("this.selected = chosen", source)
        self.assertIn("role = Role.Tab", source)
        self.assertIn('onClick(label = "Открыть $label")', source)
        self.assertNotIn('testTag("profile-tab-label-', source)


if __name__ == "__main__":
    unittest.main()

