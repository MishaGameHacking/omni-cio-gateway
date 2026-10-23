"""Keep actual network policy restrictive in app, debug and test-driver manifests."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
ANDROID = '{http://schemas.android.com/apk/res/android}'
CONFIG = '@xml/network_security_config'


class NetworkPolicyContractTests(unittest.TestCase):
    def test_every_application_declares_deny_cleartext_policy(self):
        for name in ('app/src/main', 'app/src/debug', 'ci-ui-driver/src/main'):
            with self.subTest(source=name):
                application = ET.parse(ROOT / name / 'AndroidManifest.xml').getroot().find('application')
                self.assertIsNotNone(application)
                self.assertEqual(application.get(ANDROID + 'usesCleartextTraffic'), 'false')
                self.assertEqual(application.get(ANDROID + 'networkSecurityConfig'), CONFIG)

    def test_configs_deny_cleartext_without_domain_or_debug_exceptions(self):
        for module in ('app', 'ci-ui-driver'):
            with self.subTest(module=module):
                config = ET.parse(ROOT / module / 'src/main/res/xml/network_security_config.xml').getroot()
                self.assertEqual(config.tag, 'network-security-config')
                self.assertEqual([node.tag for node in config], ['base-config'])
                base = config.find('base-config')
                self.assertEqual(base.get('cleartextTrafficPermitted'), 'false')
                anchors = base.findall('trust-anchors/certificates')
                self.assertEqual([node.attrib for node in anchors], [{'src': 'system'}])
                self.assertIsNone(config.find('domain-config'))
                self.assertIsNone(config.find('debug-overrides'))

    def test_ci_driver_does_not_acquire_network_permission(self):
        manifest = ET.parse(ROOT / 'ci-ui-driver/src/main/AndroidManifest.xml').getroot()
        names = [entry.get(ANDROID + 'name') for entry in manifest.findall('uses-permission')]
        self.assertNotIn('android.permission.INTERNET', names)

    def test_debug_cannot_shadow_main_network_security_resource(self):
        overrides = list((ROOT / 'app/src/debug').rglob('network_security_config.xml'))
        self.assertEqual(overrides, [])


if __name__ == '__main__':
    unittest.main()
