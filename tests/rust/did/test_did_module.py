#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from tests import unittest


class RustDidModuleTestCase(unittest.TestCase):
    def test_submit_did_set_builds_ledger_entry(self) -> None:
        from textrp_briij.synapse_rust import did as rust_did

        result = rust_did.submit_did_set(
            {
                "account": "rEXPLICIT111111111111111111111111111",
                "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "did_document_json": '{"id":"did:xrpl:testnet:rEXPLICIT111111111111111111111111111"}',
                "e2ee_commitment": "future-e2ee-key-commitment",
            }
        )

        self.assertEqual(result["account"], "rEXPLICIT111111111111111111111111111")
        self.assertEqual(
            result["did_uri"],
            "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
        )
        self.assertIn("ledger_hash", result)

    def test_resolve_did_document_explicit(self) -> None:
        from textrp_briij.synapse_rust import did as rust_did

        result = rust_did.resolve_did_document("rEXPLICIT111111111111111111111111111")
        self.assertEqual(result["resolution_type"], "explicit")
        self.assertEqual(
            result["did_uri"],
            "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
        )

    def test_resolve_did_document_implicit(self) -> None:
        from textrp_briij.synapse_rust import did as rust_did

        result = rust_did.resolve_did_document("rImplicit111111111111111111111111111")
        self.assertEqual(result["resolution_type"], "implicit")
        self.assertEqual(
            result["did_uri"],
            "did:xrpl:testnet:rImplicit111111111111111111111111111",
        )

    def test_verify_did_control(self) -> None:
        from textrp_briij.synapse_rust import did as rust_did

        self.assertTrue(
            rust_did.verify_did_control(
                "rEXPLICIT111111111111111111111111111",
                "valid-proof:rEXPLICIT111111111111111111111111111",
            )
        )
        self.assertFalse(
            rust_did.verify_did_control(
                "rEXPLICIT111111111111111111111111111",
                "invalid-proof",
            )
        )

    def test_resolve_did_document_rejects_invalid_account(self) -> None:
        from textrp_briij.synapse_rust import did as rust_did

        with self.assertRaises(Exception):
            rust_did.resolve_did_document("bad-account")
