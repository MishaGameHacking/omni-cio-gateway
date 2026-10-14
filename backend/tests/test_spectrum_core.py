"""Synthetic fixtures ONLY; no external services or actual investor balances."""
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest
from backend.risk_preview import (Rating, Exposure, RiskInputError, number,
    empirical_tail_risk, scenario_losses, expected_credit_loss, assess_exposures, instrument_link)
from backend.release_contract import Release, InvalidRelease, decide_client, PACKAGE, HOST

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
AGE = timedelta(days=2)


def rate(**kw):
    return replace(Rating('agency-test', 'RU-national-test', 'A', 'issuer-one',
        'synthetic-test', NOW - timedelta(days=1), NOW + timedelta(days=30)), **kw)


def position(**kw):
    return replace(Exposure('synthetic-one', 'issuer-one', 'industry', 'bond',
        'RUB', D(40), 'RUB', NOW, 'synthetic-test', rating=rate(), requires_rating=True), **kw)


def exposure_report(items, limits=None):
    return assess_exposures(items, base_currency='RUB', now=NOW,
        max_age=AGE, limits=limits or {})


def release(**kw):
    base = Release(23, 23, 'candidate-test', PACKAGE,
        f'https://{HOST}/releases/23/'+ 'a'*64 + '.apk',
        'a'*64, 'b'*64, 10_000, 33, '2026-10-13T11:00:00Z', 'Synthetic fixture')
    return replace(base, **kw)


class RiskTests(unittest.TestCase):
    def test_fractional_tail_includes_boundary(self):
        r = empirical_tail_risk([D(0),D(1),D(2),D(3)], alpha=D('.625'),
            horizon_days=1, source='synthetic', as_of=NOW, now=NOW,
            max_age=AGE, min_tail_observations=1)
        self.assertEqual(r.var_loss, D(2))
        self.assertEqual(r.expected_shortfall, D(4)/D('1.5'))

    def test_tail_all_equal(self):
        r = empirical_tail_risk([D('.02')]*100, alpha=D('.95'),
            horizon_days=1, source='synthetic', as_of=NOW, now=NOW, max_age=AGE)
        self.assertEqual(r.expected_shortfall,D('.02'))

    def test_negative_losses_are_not_clamped(self):
        r = empirical_tail_risk([D('-.02')]*100, alpha=D('.95'),
            horizon_days=1, source='synthetic', as_of=NOW, now=NOW, max_age=AGE)
        self.assertEqual(r.expected_shortfall,D('-.02'))

    def test_insufficient_history_not_reported_as_confidence(self):
        losses, confidence = [D(0)] * 20, D('.99')
        with self.assertRaises(RiskInputError):
            empirical_tail_risk(losses, alpha=confidence, horizon_days=1,
                source='synthetic', as_of=NOW, now=NOW, max_age=AGE)

    def test_stale_history_rejected(self):
        losses, confidence = [D(0)] * 100, D('.95')
        stale = NOW - timedelta(days=3)
        with self.assertRaises(RiskInputError):
            empirical_tail_risk(losses, alpha=confidence, horizon_days=1,
                source='synthetic', as_of=stale, now=NOW, max_age=AGE)

    def test_invalid_confidence_rejected(self):
        losses = [D(0)] * 100
        for alpha in ['0', '1', 'NaN', 'Infinity', '-.1']:
            confidence = D(alpha)
            with self.subTest(alpha=alpha), self.assertRaises(RiskInputError):
                empirical_tail_risk(losses, alpha=confidence, horizon_days=1,
                    source='synthetic', as_of=NOW, now=NOW, max_age=AGE)

    def test_joint_scenarios_preserve_dependence(self):
        result = scenario_losses({'a':D('.5'),'b':D('.5')},
            [{'a':D('-.1'),'b':D('.1')},{'a':D('.2'),'b':D('-.2')}])
        self.assertEqual(result,(D(0),D(0)))

    def test_missing_asset_rejected(self):
        weights = {'a': D('.5'), 'b': D('.5')}
        scenarios = [{'a': D(0)}]
        with self.assertRaises(RiskInputError):
            scenario_losses(weights, scenarios)

    def test_empty_scenarios_and_invalid_asset_ids_rejected(self):
        valid_weights = {'a': D(1)}
        with self.assertRaises(RiskInputError):
            scenario_losses(valid_weights, [])
        for weights, scenarios in [({'':D(1)},[{'':D(0)}]), ({None:D(1)},[{None:D(0)}])]:
            with self.subTest(weights=weights), self.assertRaises(RiskInputError):
                scenario_losses(weights, scenarios)

    def test_weights_and_returns_checked(self):
        for weights, scenarios in [({'a':D('.5')},[{'a':D(0)}]),
            ({'a':D(1)},[{'a':D(-2)}]), ({'a':D(-1)},[{'a':D(0)}])]:
            with self.assertRaises(RiskInputError): scenario_losses(weights,scenarios)

    def test_expected_loss_only_explicit_inputs(self):
        self.assertEqual(expected_credit_loss(D(1000), D('.02'), D('.6')), D(12))
        exposure, probability, loss_fraction = D(100), D(2), D('.6')
        with self.assertRaises(RiskInputError):
            expected_credit_loss(exposure, probability, loss_fraction)

    def test_no_binary_float_or_nonfinite(self):
        for value in [1.1,True,'NaN','Infinity',None]:
            with self.subTest(value=value), self.assertRaises(RiskInputError): number(value)

    def test_group_aggregates_across_accounts(self):
        r = exposure_report([position(), position(instrument_id='other',value_base=D(60))],
            {'issuer:issuer-one':D('.5')})
        self.assertEqual(r['shares']['issuer:issuer-one'],D(1))
        self.assertEqual(len(r['violations']),1)

    def test_cash_not_counted_as_security(self):
        r = exposure_report([position(is_cash=True,requires_rating=False,issuer_group='')])
        self.assertFalse(any(k.startswith('issuer:') for k in r['shares']))

    def test_reserve_breach(self):
        r = exposure_report([position()],{'cash:minimum':D('.1')})
        self.assertEqual(r['status'],'outside_limits')

    def test_invalid_limit_dimension_rejected(self):
        items, cap = [position()], D('.5')
        for key in ['', 'cash:maximum', 'issuerr:issuer-one', 'issuer:', None]:
            with self.subTest(key=key), self.assertRaises(RiskInputError):
                exposure_report(items, {key: cap})

    def test_rating_agency_and_scale_not_merged(self):
        r = exposure_report([position(), position(rating=rate(scale='GLOBAL-test'))])
        self.assertEqual(len([k for k in r['shares'] if k.startswith('rating:')]),2)

    def test_unknown_rating_not_safest_bucket(self):
        for rating in [None,rate(withdrawn=True),rate(valid_until=NOW),rate(subject_id='someone-else')]:
            with self.subTest(rating=rating):
                self.assertEqual(exposure_report([position(rating=rating)])['status'],'needs_data')

    def test_missing_class_or_quote_currency_needs_data(self):
        for item in [position(asset_class=''), position(quote_currency='')]:
            with self.subTest(item=item):
                report = exposure_report([item])
                self.assertEqual(report['status'], 'needs_data')
                self.assertEqual(report['unverified_instruments'], ['synthetic-one'])

    def test_invalid_base_or_quote_currency_rejected(self):
        items = [position()]
        for currency in ['', 'rub', 'RUBLE', None]:
            with self.subTest(base=currency), self.assertRaises(RiskInputError):
                assess_exposures(items, base_currency=currency, now=NOW,
                    max_age=AGE, limits={})
        for currency in ['rub', 'RUBLE', '12R']:
            items = [position(quote_currency=currency)]
            with self.subTest(quote=currency), self.assertRaises(RiskInputError):
                exposure_report(items)

    def test_mixed_currency_not_added(self):
        items = [position(valuation_currency='USD')]
        with self.assertRaises(RiskInputError):
            exposure_report(items)

    def test_negative_position_rejected(self):
        items = [position(value_base=D(-1))]
        with self.assertRaises(RiskInputError):
            exposure_report(items)

    def test_future_or_stale_valuation_rejected(self):
        for at in [NOW + timedelta(seconds=1), NOW - timedelta(days=10)]:
            items = [position(valuation_at=at)]
            with self.assertRaises(RiskInputError):
                exposure_report(items)

    def test_rating_naive_date_rejected(self):
        item = rate(published_at=NOW.replace(tzinfo=None))
        with self.assertRaises(RiskInputError):
            item.bucket(NOW)

    def test_link_only_canonical_card(self):
        self.assertEqual(instrument_link('https://www.tbank.ru/invest/stocks/SBER/'),
            'https://www.tbank.ru/invest/stocks/SBER/')
        for url in ['http://www.tbank.ru/invest/stocks/SBER/',
                    'https://www.tbank.ru@evil.test/invest/stocks/SBER/',
                    'https://www.tbank.ru/invest/stocks/SBER/?buy=1',
                    'https://www.tbank.ru/invest/stocks/../',
                    'https://evil.test/invest/stocks/SBER/']:
            with self.assertRaises(RiskInputError): instrument_link(url)


class ReleaseTests(unittest.TestCase):
    def test_release_validates(self):
        self.assertEqual(Release.parse(asdict(release()), now=NOW,expected_certificate='b'*64),release())

    def test_never_activate_unavailable_distribution(self):
        result = decide_client(release(), installed_code=22,sdk=33,package_name=PACKAGE,distribution_verified=False)
        self.assertEqual(result.state,'service_unavailable')
        self.assertNotEqual(result.reason,'minimum_supported_version')

    def test_old_client_blocked(self):
        result = decide_client(release(), installed_code=22,sdk=33,package_name=PACKAGE,distribution_verified=True)
        self.assertEqual(result.state,'update_required')
        self.assertFalse(result.allow_personal_analysis)

    def test_current_resumes(self):
        result = decide_client(release(), installed_code=23,sdk=33,package_name=PACKAGE,distribution_verified=True)
        self.assertEqual(result.state,'current')
        self.assertTrue(result.allow_personal_analysis)

    def test_legacy_not_current(self):
        self.assertEqual(decide_client(release(), installed_code=None,sdk=33,
            package_name=PACKAGE,distribution_verified=True).state,'unknown_client')

    def test_future_not_implicitly_trusted(self):
        self.assertEqual(decide_client(release(), installed_code=999,sdk=33,
            package_name=PACKAGE,distribution_verified=True).state,'unknown_future_version')

    def test_optional_rollout(self):
        self.assertEqual(decide_client(release(minimum_supported=22),installed_code=22,sdk=33,
            package_name=PACKAGE,distribution_verified=True).state,'update_available')

    def test_wrong_package_and_os(self):
        self.assertEqual(decide_client(release(), installed_code=23,sdk=32,
            package_name=PACKAGE,distribution_verified=True).state,'unsupported_device')
        self.assertEqual(decide_client(release(), installed_code=23,sdk=33,
            package_name='ru.omnicio.app',distribution_verified=True).state,'wrong_package')

    def test_bad_release_inputs(self):
        variants = [dict(version_code=True),dict(minimum_supported=24),dict(size_bytes=0),
            dict(certificate_sha256='c'*64),dict(sha256='bad'),dict(package_name='other'),
            dict(published_at='2027-01-01T00:00:00Z'),dict(published_at='2026-10-13'),
            dict(url=f'http://{HOST}/releases/23/'+ 'a'*64 + '.apk'),
            dict(url=f'https://{HOST}/releases/23/latest.apk'),dict(notes=123),
            dict(version_name='bad\nname'),dict(notes='bad\x00notes')]
        for change in variants:
            candidate = asdict(release(**change))
            with self.subTest(change=change), self.assertRaises(InvalidRelease):
                Release.parse(candidate, now=NOW, expected_certificate='b'*64)

    def test_direct_validation_requires_aware_time(self):
        candidate, naive = release(), NOW.replace(tzinfo=None)
        with self.assertRaises(InvalidRelease):
            candidate.validate(now=naive, expected_certificate='b'*64)

    def test_distribution_verification_must_be_boolean(self):
        candidate = release()
        with self.assertRaises(InvalidRelease):
            decide_client(candidate, installed_code=23, sdk=33,
                package_name=PACKAGE, distribution_verified='yes')

    def test_bool_version_does_not_bypass_gate(self):
        candidate = release()
        with self.assertRaises(InvalidRelease):
            decide_client(candidate, installed_code=True, sdk=33,
                package_name=PACKAGE, distribution_verified=True)


if __name__ == '__main__': unittest.main()
