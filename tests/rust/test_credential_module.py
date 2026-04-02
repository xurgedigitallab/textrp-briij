#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from tests import unittest


class RustCredentialModuleTestCase(unittest.TestCase):
    def test_submit_credential_create(self) -> None:
        from textrp_briij.synapse_rust import credential as rust_credential

        credential = rust_credential.submit_credential_create(
            {
                "subject": "rEXPLICIT111111111111111111111111111",
                "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "matrix_user_id": "@alice:test",
                "e2ee_pubkey_commitment": "abc123",
            }
        )
        self.assertEqual(
            credential["subject"], "rEXPLICIT111111111111111111111111111"
        )
        self.assertIn("credential_id", credential)
        self.assertEqual(credential["status"], "issued")

    def test_verify_credential(self) -> None:
        from textrp_briij.synapse_rust import credential as rust_credential

        issued = rust_credential.submit_credential_create(
            {
                "subject": "rEXPLICIT111111111111111111111111111",
                "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "matrix_user_id": "@alice:test",
                "e2ee_pubkey_commitment": "abc123",
            }
        )
        self.assertTrue(rust_credential.verify_credential(issued["credential_id"]))

    def test_revoke_credential(self) -> None:
        from textrp_briij.synapse_rust import credential as rust_credential

        issued = rust_credential.submit_credential_create(
            {
                "subject": "rEXPLICIT111111111111111111111111111",
                "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "matrix_user_id": "@alice:test",
                "e2ee_pubkey_commitment": "abc123",
            }
        )
        revoked = rust_credential.submit_credential_delete(
            {"credential_id": issued["credential_id"]}
        )
        self.assertEqual(revoked["status"], "revoked")
        self.assertFalse(rust_credential.verify_credential(issued["credential_id"]))

    def test_invalid_proof_or_subject_rejected(self) -> None:
        from textrp_briij.synapse_rust import credential as rust_credential

        with self.assertRaises(Exception):
            rust_credential.submit_credential_create(
                {
                    "subject": "bad-address",
                    "did_uri": "did:xrpl:testnet:bad-address",
                    "matrix_user_id": "@alice:test",
                    "e2ee_pubkey_commitment": "abc123",
                }
            )
