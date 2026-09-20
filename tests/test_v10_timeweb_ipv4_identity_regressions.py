from __future__ import annotations

from dataclasses import fields
import hashlib
import unittest

from scripts import provision_v10_timeweb_postgres_public_ipv4_tls as transport
from scripts import timeweb_ipv4_custody as custody


def _row(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "synthetic-ip-1",
        "ip": "8.8.4.4",
        "availability_zone": "msk-1",
        "is_ddos_guard": False,
        "resource_type": None,
        "resource_id": None,
        "comment": "",
    }
    value.update(changes)
    return value


class TimewebIpv4IdentityRegressionTests(unittest.TestCase):
    def test_transport_accepts_canonical_ascii_integer_identifiers(self) -> None:
        for value in (1, 91, "1", "91", "9" * 20):
            with self.subTest(value=value):
                self.assertEqual(
                    transport._numeric_id(value, "TARGET_INVALID"), int(value)
                )

    def test_transport_rejects_unicode_digits_in_every_position(self) -> None:
        # Unicode decimal digits must not broaden the provider identity boundary.
        for digit in ("\u0661", "\u06f1", "\uff11", "\U0001d7cf"):
            for value in (digit, digit + "1", "1" + digit, "1" + digit + "1"):
                with self.subTest(value=value):
                    with self.assertRaises(
                        transport._provider_base.ProvisioningStopped
                    ):
                        transport._numeric_id(value, "TARGET_INVALID")

    def test_transport_keeps_length_padding_and_type_rejections(self) -> None:
        invalid = (True, False, 91.0, 1.5, 0, -1, "0", "091", " 91", "91\n", "9" * 21)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(transport._provider_base.ProvisioningStopped):
                    transport._numeric_id(value, "TARGET_INVALID")

    def test_binding_parser_preserves_database_aliases_and_ascii_identity(self) -> None:
        for kind in ("database", "dbaas"):
            for value in (91, "91"):
                payload = [_row(resource_type=kind, resource_id=value)]
                with self.subTest(kind=kind, value=value):
                    actual = custody.inventory(payload)[0]
                    self.assertEqual(actual.resource_id, "91")
                    self.assertFalse(actual.unbound)

    def test_binding_parser_rejects_non_ascii_digits_without_normalizing(self) -> None:
        for kind in ("database", "dbaas"):
            invalid = ("9\u0661", "9\u06f1", "9\uff11", "9\U0001d7cf", "\u06691")
            for value in invalid:
                payload = [_row(resource_type=kind, resource_id=value)]
                with self.subTest(kind=kind, value=value):
                    with self.assertRaisesRegex(
                        custody.CustodyStopped, "BINDING_STATE_UNKNOWN"
                    ):
                        custody.inventory(payload)

    def test_field_rename_preserves_v1_marker_preimage(self) -> None:
        # Fixed synthetic protocol input, independent of dataclass field names.
        preimage = (
            b'["MishaGameHacking/omni-cio-gateway","RU-PG-B",'
            b'"omni-cio-v10-ru-pg-synthetic","91","msk-1",'
            b'"synthetic-ip-1","8.8.4.4"]'
        )
        expected = "omni-cio:ru-pg-b:ipv4:v1:" + hashlib.sha256(preimage).hexdigest()
        actual = custody.inventory([_row()])[0]
        self.assertEqual(actual.ip_address, "8.8.4.4")
        self.assertEqual(custody.marker(91, actual), expected)
        names = {field.name for field in fields(custody.Address)}
        self.assertIn("ip_address", names)
        self.assertNotIn("address", names)

    def test_renamed_field_preserves_recovery_and_private_evidence_boundary(
        self,
    ) -> None:
        row = _row()
        parsed = custody.inventory([row])[0]
        row["comment"] = custody.marker(91, parsed)
        rows = custody.inventory([row])
        selected = custody.select(rows, 91, public_enabled=False)
        self.assertEqual(selected, rows[0])
        output = custody.observation(rows, 91) + repr(rows[0])
        for private_value in (row["id"], row["ip"], row["comment"]):
            self.assertNotIn(private_value, output)
        self.assertIn("managed_unbound=1", output)


if __name__ == "__main__":
    unittest.main()
