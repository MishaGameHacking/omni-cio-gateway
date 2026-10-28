"""Source-boundary regressions, not a replacement for device self-update tests."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
NATIVE = ROOT / 'app/src/main/java/ru/omnicio/app'
ANDROID = '{http://schemas.android.com/apk/res/android}'


class UnifiedUpdateContractTests(unittest.TestCase):
    def source(self, path):
        return (NATIVE / path).read_text(encoding='utf-8')

    def test_single_runtime_updater(self):
        names = {p.name for p in (NATIVE / 'data/updates').glob('*.kt')}
        self.assertLessEqual({'UpdateClient.kt', 'UpdateInstaller.kt', 'UpdateProtocol.kt'}, names)
        self.assertTrue(names.isdisjoint({'AppRelease.kt', 'AppUpdateClient.kt', 'AppUpdateInstaller.kt', 'AppUpdateVerifier.kt', 'UpdateCheckStore.kt'}))

    def test_no_legacy_network_update_contract_in_app(self):
        for path in NATIVE.rglob('*.kt'):
            with self.subTest(path=path.name):
                self.assertNotIn('/releases/current.json', path.read_text(encoding='utf-8'))

    def test_main_uses_shared_gate_and_spectrum_renderer(self):
        main = self.source('MainActivity.kt')
        self.assertIn('MandatoryUpdateHost(blockedContent =', main)
        self.assertIn('RequiredUpdateScreen(state, actions, extraContent = { OfflineSnapshotAccess(state) })', main)
        self.assertIn('AnalystAiApp(', main)

    def test_bootstrap_does_not_forward_untrusted_extras_or_check_a_second_policy(self):
        source = self.source('BootstrapActivity.kt')
        self.assertIn('MainActivity::class.java', source)
        for forbidden in ('putExtras', 'getBooleanExtra', 'UpdateCheckStore', 'fetchRelease', 'openConnection'):
            self.assertNotIn(forbidden, source)
        self.assertIn('it.scheme == "analystai" && it.host == "auth"', source)

    def test_application_has_no_second_lifecycle_gate(self):
        source = self.source('AnalystApplication.kt')
        self.assertNotIn('registerActivityLifecycleCallbacks', source)
        self.assertNotIn('UpdateCheckStore', source)

    def test_telegram_return_is_preserved(self):
        source = self.source('MainActivity.kt')
        for token in ('captureTelegramCallback', 'AUTH_SCHEME = "analystai"', 'AUTH_HOST = "auth"', 'exchangeTelegramCode(code)', 'sessionStore.save(result.value)'):
            self.assertIn(token, source)


    def test_spectrum_primary_navigation_and_internal_destinations(self):
        main = self.source('MainActivity.kt')
        bar = self.source('ui/AnalystBottomBar.kt')
        catalogue = self.source('ui/NavigationCatalogue.kt')
        self.assertIn('analystPrimaryDestinations.mapNotNull { it.tab }', bar)
        self.assertIn('SpectrumGlyphButton',bar)
        self.assertNotIn('AnalystMenuButton(openMenu)',bar)
        for tab,label,screen in (('Home','Главная','Home'),('Portfolio','Портфель','Portfolio'),
                                 ('Actions','Решения','Recommendations'),('Profile','Настройки','Profile')):
            self.assertIn('AnalystDestination("'+screen+'", "'+label+'"',catalogue)
            self.assertIn('AnalystTab.'+tab+' -> AppScreen.'+screen,main)
        for tab in ('Risk','Education'):
            self.assertIn('AnalystTab.'+tab+' -> AppScreen.'+tab,main)
        for screen in ('Recommendations', 'Messages'):
            self.assertIn('AppScreen.' + screen, main)
        self.assertIn('AutonomousDecisionsScreen(goBack)', main)
        for forbidden in ('AnalystTab.Ideas', 'AnalystTab.Pulse', 'AnalystTab.Chat'):
            self.assertNotIn(forbidden, main)


    def test_home_uses_server_saved_automation_state_without_demo_balances(self):
        main = self.source('MainActivity.kt')
        source = self.source('ui/home/HomeScreen.kt')
        home = source.split('fun HomeScreen(', 1)[1].split('\nprivate fun automationStateTitle', 1)[0]
        self.assertIn('HomeScreen(', main)
        for token in ('rememberWorkspaceResource("/automation/status")',
                      'resource.data?.takeIf { it.optInt("schema_version") == 1 }',
                      'status?.records("blockers")', 'status?.optJSONObject("discovery")',
                      'discovery?.records("candidates")', 'status?.text("last_observation_at", "")',
                      'HomeAutomationCard(status, resource.error, resource.busy, resource.refresh',
                      'val currentError = error',
                      'execution?.text("mode", "") == "read_only"',
                      'execution.opt("real_orders_enabled") == false'):
            self.assertIn(token, home)
        for forbidden in ('snapshot.totalValue', 'snapshot.allocations', 'InteractiveBalance(',
                          'HoldToRevealBalance(', 'PortfolioSnapshot(', 'rememberWorkspaceAction(',
                          '1 238 532', 'SBER', 'TBru', 'YDEX', 'demoBalance', 'fixtureBalance'):
            self.assertNotIn(forbidden, home)
        self.assertIn('status == null -> "Получаем состояние"', home)
        self.assertIn('Новых проверенных решений пока нет.', home)

    def test_network_clients_send_same_version_and_handle_426(self):
        for file in ('data/backend/AnalystBackendClient.kt', 'data/analysis/AnalysisBackendClient.kt', 'data/portfolio/PortfolioDataClient.kt'):
            source = self.source(file)
            with self.subTest(file=file):
                self.assertIn('ClientVersion.attach', source)
                self.assertIn('ClientVersion.observeStatus', source)
                self.assertIn('426', source)

    def test_spectrum_is_presentation_not_installer(self):
        source = self.source('ui/spectrum/RequiredUpdateScreen.kt')
        for forbidden in ('PackageInstaller', 'openConnection', 'AuthSessionStore', 'verifiedCurrent()', 'AppRelease'):
            self.assertNotIn(forbidden, source)
        self.assertIn('UpdateGateUi', source)
        self.assertIn('UpdateGateActions', source)

    def test_safe_areas_and_optional_motion(self):
        source = self.source('ui/spectrum/RequiredUpdateScreen.kt')
        self.assertIn('safeDrawingPadding()', source)
        self.assertIn('motionAllowed = motion.enabled', source)
        self.assertIn('LocalSpectrumMotionPreference', source)
        self.assertIn('heightIn(min = 48.dp)', source)

    def test_install_receivers_are_private(self):
        app = ET.parse(ROOT / 'app/src/main/AndroidManifest.xml').getroot().find('application')
        receivers = {item.get(ANDROID + 'name'): item for item in app.findall('receiver')}
        for name in ('.data.updates.InstallResultReceiver', '.data.updates.AppReplacedReceiver'):
            self.assertEqual(receivers[name].get(ANDROID + 'exported'), 'false')
        self.assertNotIn('.data.updates.UpdateInstallReceiver', receivers)

    def test_only_bootstrap_is_exported(self):
        app = ET.parse(ROOT / 'app/src/main/AndroidManifest.xml').getroot().find('application')
        activities = {item.get(ANDROID + 'name'): item for item in app.findall('activity')}
        self.assertEqual(activities['.BootstrapActivity'].get(ANDROID + 'exported'), 'true')
        self.assertEqual(activities['.MainActivity'].get(ANDROID + 'exported'), 'false')
        data = activities['.BootstrapActivity'].findall('intent-filter/data')
        self.assertTrue(any(item.get(ANDROID + 'scheme') == 'analystai' and item.get(ANDROID + 'host') == 'auth' for item in data))

    def test_server_canonical_modules_are_present(self):
        for name in ('client_updates.py', 'client_compatibility.py', 'release_publication.py', 'release_lock.py', 'portfolio_risk.py', 'risk_preview.py', 'release_contract.py'):
            self.assertTrue((ROOT / 'backend' / name).is_file(), name)

    def test_regression_fixture_runs_shared_and_spectrum_checks(self):
        fixture = (ROOT / 'app/src/debug/java/ru/omnicio/app/ProfileUiProbeActivity.kt').read_text(encoding='utf-8')
        for call in ('runRefreshStateRegressionChecks()', 'runEducationCatalogChecks()', 'runUpdatePolicyChecks()', 'runInstallStreamChecks()', 'runUpdateProtocolChecks()', 'runUpdateDownloadChecks()', 'runUpdateGateUiChecks()'):
            self.assertIn(call, fixture)


if __name__ == '__main__':
    unittest.main()

