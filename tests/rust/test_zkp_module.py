#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from tests import unittest


class RustZkpModuleTestCase(unittest.TestCase):
    def test_verify_zkp_binding_valid(self) -> None:
        from textrp_briij.synapse_rust import zkp as rust_zkp

        result = rust_zkp.verify_zkp_binding(
            {
                "proof": {"type": "groth16", "subject": "rEXPLICIT111111111111111111111111111"},
                "public_signals": {
                    "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                    "xrpl_address": "rEXPLICIT111111111111111111111111111",
                    "credential_id": "cred-123",
                    "e2ee_pubkey_commitment": "abc123",
                },
                "expected_did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "expected_xrpl_address": "rEXPLICIT111111111111111111111111111",
                "expected_credential_id": "cred-123",
                "expected_e2ee_pubkey_commitment": "abc123",
            }
        )
        self.assertTrue(result["valid"])
        self.assertIn("verified_at", result)

    def test_verify_zkp_binding_invalid(self) -> None:
        from textrp_briij.synapse_rust import zkp as rust_zkp

        result = rust_zkp.verify_zkp_binding(
            {
                "proof": {"type": "groth16"},
                "public_signals": {
                    "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                    "xrpl_address": "rEXPLICIT111111111111111111111111111",
                    "credential_id": "cred-123",
                    "e2ee_pubkey_commitment": "different",
                },
                "expected_did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "expected_xrpl_address": "rEXPLICIT111111111111111111111111111",
                "expected_credential_id": "cred-123",
                "expected_e2ee_pubkey_commitment": "abc123",
            }
        )
        self.assertFalse(result["valid"])
