"""Merged routing: real auth/version dependency, no broker or model calls."""
from contextlib import closing
import unittest
from unittest.mock import patch

from backend.tests import test_update_integration as fixtures
from backend import app as backend, portfolio_research as research


class ResearchUpdateGateTests(unittest.TestCase):
    setUp = fixtures.ApplicationUpdateTests.setUp
    tearDown = fixtures.ApplicationUpdateTests.tearDown
    publish = fixtures.ApplicationUpdateTests.publish
    headers = fixtures.ApplicationUpdateTests.headers

    def test_route_is_registered_once(self):
        routes = [route for route in backend.app.routes if getattr(route, 'path', '') == '/analysis/research']
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].methods, {'GET'})

    def test_authentication_precedes_research_and_version(self):
        with patch.object(research, 'collect_research') as collect:
            response = self.client.get('/analysis/research', headers={'X-Analyst-Version-Code': '22'})
        self.assertEqual(response.status_code, 401)
        collect.assert_not_called()

    def test_old_version_stops_research_before_collection(self):
        with patch.object(research, 'collect_research') as collect:
            response = self.client.get('/analysis/research', headers=self.headers(22))
        self.assertEqual(response.status_code, 426)
        self.assertEqual(response.json()['detail']['code'], 'client_update_required')
        collect.assert_not_called()
        with closing(backend.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT tinvest_token_encrypted FROM users').fetchone()[0], b'fake-only')

    def test_new_release_blocks_previously_current_research_client(self):
        self.assertEqual(self.client.post('/client/ready', headers=self.headers()).status_code, 200)
        self.publish(24)
        with patch.object(research, 'collect_research') as collect:
            response = self.client.get('/analysis/research', headers=self.headers(23))
        self.assertEqual(response.status_code, 426)
        collect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
