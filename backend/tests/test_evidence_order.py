from copy import deepcopy
from datetime import datetime, timezone
import unittest

from backend.evidence_order import latest_unambiguous

NOW = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)


def fact(issuer="issuer-a", **source):
    return {"instrument_uid": "instrument-a", "issuer_id": issuer, "source": {
        "id": "s1", "review_id": "r1", "url": "https://example.org/report",
        "published_at": "2026-10-12T10:00:00Z",
        "checked_at": "2026-10-13T10:00:00Z",
        "expires_at": "2026-10-15T10:00:00Z", **source}}


def valid(source):
    return bool(source.get("review_id")) and datetime.fromisoformat(
        source["expires_at"].replace("Z", "+00:00")) > NOW


class EvidenceOrderTests(unittest.TestCase):
    def select(self, records):
        return latest_unambiguous(records, at=NOW, valid_source=valid)

    def test_empty(self):
        self.assertIsNone(self.select([]))

    def test_single(self):
        self.assertEqual(self.select([fact()]), fact())

    def test_latest_publication_not_import_order(self):
        older = fact("old", published_at="2026-10-11T10:00:00Z")
        for records in ([older, fact()], [fact(), older]):
            self.assertEqual(self.select(records)["issuer_id"], "issuer-a")

    def test_identity_conflict_is_not_row_order_dependent(self):
        for records in ([fact(), fact("other")], [fact("other"), fact()]):
            self.assertIsNone(self.select(records))

    def test_statement_values_conflict(self):
        first, second = fact(), fact()
        first["values"], second["values"] = {"debt": "100"}, {"debt": "10"}
        self.assertIsNone(self.select([first, second]))

    def test_total_return_conflict(self):
        first, second = fact(), fact()
        first["values"], second["values"] = {"2026-10-10": .01}, {"2026-10-10": -.01}
        self.assertIsNone(self.select([first, second]))

    def test_duplicate_audit_ids_are_not_material_conflicts(self):
        repeated = fact(id="s2", review_id="r2")
        self.assertEqual(self.select([repeated, fact()]), fact())

    def test_duplicate_choice_is_stable(self):
        repeated = fact(id="s2", review_id="r2")
        self.assertEqual(self.select([repeated, fact()]), self.select([fact(), repeated]))

    def test_different_expiry_is_conflict(self):
        self.assertIsNone(self.select([fact(), fact(expires_at="2026-10-14T10:00:00Z")]))

    def test_expired_latest_never_restores_old_fact(self):
        older = fact("old", published_at="2026-10-11T10:00:00Z")
        expired = fact(expires_at="2026-10-13T11:00:00Z")
        self.assertIsNone(self.select([older, expired]))

    def test_invalid_duplicate_cannot_be_hidden(self):
        self.assertIsNone(self.select([fact(), fact(review_id="")]))

    def test_malformed_date_cannot_restore_old(self):
        self.assertIsNone(self.select([fact(), fact(published_at="invalid")]))

    def test_future_observation_is_not_current(self):
        later = fact("future", published_at="2026-10-14T10:00:00Z",
                     checked_at="2026-10-14T11:00:00Z")
        self.assertEqual(self.select([later, fact()]), fact())

    def test_checked_before_published_rejected(self):
        self.assertIsNone(self.select([fact(checked_at="2026-10-11T10:00:00Z")]))

    def test_assessment_timezone_required(self):
        records = [fact()]
        naive = NOW.replace(tzinfo=None)
        with self.assertRaises(ValueError):
            latest_unambiguous(records, at=naive, valid_source=valid)

    def test_nonfinite_payload_rejected(self):
        item = fact()
        item["value"] = float("nan")
        self.assertIsNone(self.select([item]))

    def test_source_constructor_error_fails_closed(self):
        def broken(_):
            raise TypeError("invalid source")
        self.assertIsNone(latest_unambiguous([fact()], at=NOW, valid_source=broken))

    def test_input_not_mutated(self):
        items = [fact()]
        before = deepcopy(items)
        self.select(items)
        self.assertEqual(items, before)


if __name__ == "__main__":
    unittest.main()
