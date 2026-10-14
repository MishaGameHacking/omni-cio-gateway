"""Synthetic configuration fingerprints. No requests to broker or model providers."""
from copy import deepcopy
import unittest
from backend.research_profile_cache import profile_digest


class ProfileCacheTests(unittest.TestCase):
    def test_same_profile_has_stable_fingerprint(self):
        profile = {'configured': True, 'max_position_percent': 25, 'updated_at': 1}
        self.assertEqual(profile_digest(profile), profile_digest(dict(profile)))

    def test_key_order_is_not_a_change(self):
        self.assertEqual(profile_digest({'a': 1, 'b': 2}), profile_digest({'b': 2, 'a': 1}))

    def test_same_second_limit_change_invalidates(self):
        first = {'max_position_percent': 25, 'updated_at': 1}
        second = {'max_position_percent': 10, 'updated_at': 1}
        self.assertNotEqual(profile_digest(first), profile_digest(second))

    def test_configured_transition_invalidates(self):
        self.assertNotEqual(profile_digest({'configured': False}), profile_digest({'configured': True}))

    def test_other_profile_settings_are_not_ignored(self):
        base = {'horizon': 'long', 'min_cash_percent': 5, 'allowed_markets': ['RU']}
        for key, value in (('horizon', 'short'), ('min_cash_percent', 20), ('allowed_markets', ['RU', 'OTHER'])):
            self.assertNotEqual(profile_digest(base), profile_digest({**base, key: value}))

    def test_nan_is_not_a_valid_profile(self):
        profile = {'max_position_percent': float('nan')}
        with self.assertRaises(ValueError):
            profile_digest(profile)

    def test_nonmapping_rejected(self):
        for profile in (None, [], 'profile'):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                profile_digest(profile)

    def test_input_not_mutated(self):
        profile = {'allowed_markets': ['RU'], 'max_position_percent': 25}
        original = deepcopy(profile)
        profile_digest(profile)
        self.assertEqual(profile, original)


if __name__ == '__main__':
    unittest.main()
