from dataclasses import replace
from datetime import datetime, timezone
import unittest
from backend.credit_evidence import Rating, Source, Statement, EvidenceError, credit_assessment, statement_analysis

NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)
SRC = Source('r1', 'https://acra-ratings.ru/ratings/issuer', '2026-10-10T00:00:00Z',
             '2026-10-11T00:00:00Z', '2026-11-11T00:00:00Z', 'review1')
ACTIVE = Rating('ACRA', 'RU_NATIONAL_LONG_TERM', 'AAA(RU)', 'issue', 'bond1', 'active', 'stable', SRC)


def assess(ratings):
    return credit_assessment(ratings, issuer_id='issuer1', instrument_id='bond1', at=NOW, bond=True)


class CreditConflictTests(unittest.TestCase):
    def test_withdrawal_tie_is_order_independent(self):
        withdrawn = replace(ACTIVE, status='withdrawn')
        left, right = assess([ACTIVE, withdrawn]), assess([withdrawn, ACTIVE])
        self.assertEqual(left, right)
        self.assertFalse(left['has_required_rating'])
        self.assertTrue(any('противоречивые' in warning for warning in left['warnings']))

    def test_grade_tie_is_not_best_rating_selection(self):
        self.assertFalse(assess([ACTIVE, replace(ACTIVE, grade='B(RU)')])['has_required_rating'])

    def test_outlook_tie_is_not_silently_resolved(self):
        self.assertFalse(assess([ACTIVE, replace(ACTIVE, outlook='negative')])['has_required_rating'])

    def test_older_favorable_rating_not_resurrected(self):
        older = replace(ACTIVE, source=replace(SRC, published_at='2026-09-01T00:00:00Z'))
        result = assess([older, ACTIVE, replace(ACTIVE, status='withdrawn')])
        self.assertEqual(result['ratings'], [])

    def test_later_action_supersedes_old_conflict(self):
        new = replace(ACTIVE, grade='AA(RU)', source=replace(SRC, published_at='2026-10-12T00:00:00Z', checked_at='2026-10-12T01:00:00Z'))
        result = assess([ACTIVE, replace(ACTIVE, status='withdrawn'), new])
        self.assertTrue(result['has_required_rating'])
        self.assertEqual(result['ratings'][0]['grade'], 'AA(RU)')

    def test_identical_facts_are_deduplicated_stably(self):
        duplicate = replace(ACTIVE, source=replace(SRC, id='r2', review_id='review2'))
        result = assess([ACTIVE, duplicate])
        self.assertEqual(result, assess([duplicate, ACTIVE]))
        self.assertEqual(len(result['ratings']), 1)

    def test_two_agencies_are_separate(self):
        other = replace(ACTIVE, agency='EXPERT_RA', grade='ruA', source=replace(SRC, url='https://raexpert.ru/ratings/test'))
        result = assess([ACTIVE, other])
        self.assertEqual(len(result['ratings']), 2)
        self.assertIsNone(result['default_probability'])

    def test_withdrawn_null_grade_does_not_crash_or_revive(self):
        result = assess([replace(ACTIVE, grade=None, status='withdrawn')])
        self.assertFalse(result['has_required_rating'])

    def test_bad_grade_or_url_is_not_safe(self):
        self.assertIsNone(replace(ACTIVE, grade=None).level())
        self.assertIsNone(replace(ACTIVE, source=replace(SRC, url='https://[')).level())
        self.assertFalse(replace(SRC, url=None).valid(NOW))

    def test_naive_assessment_is_domain_error(self):
        naive = NOW.replace(tzinfo=None)
        with self.assertRaises(EvidenceError):
            credit_assessment([ACTIVE], issuer_id='issuer1', instrument_id='bond1', at=naive, bond=True)

    def test_malformed_time_cannot_resurrect_older_rating(self):
        bad = replace(ACTIVE, source=replace(SRC, published_at='invalid'))
        self.assertFalse(assess([ACTIVE, bad])['has_required_rating'])

    def test_audited_string_not_treated_as_true(self):
        statement = Statement('issuer1', 'industrial', 'IFRS', 'RUB', '2026-01-01T00:00:00Z',
                              '2026-06-30T00:00:00Z', {'ebit':'100', 'interest_expense':'20'}, SRC, audited='false')
        with self.assertRaisesRegex(EvidenceError, 'audited_boolean_required'):
            statement_analysis(statement, issuer_id='issuer1', at=NOW)

    def test_future_actions_do_not_change_asof_assessment(self):
        future = replace(ACTIVE, status='withdrawn', source=replace(SRC, published_at='2027-01-01T00:00:00Z', checked_at='2027-01-02T00:00:00Z'))
        self.assertTrue(assess([ACTIVE, future])['has_required_rating'])

if __name__ == '__main__':
    unittest.main()
