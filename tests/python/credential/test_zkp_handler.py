#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

import asyncio
from unittest.mock import AsyncMock, Mock

from tests import unittest


class ZkpHandlerTestCase(unittest.TestCase):
    def test_verify_updates_user_did_map(self) -> None:
        from textrp_briij.handlers import zkp as zkp_module
        from textrp_briij.handlers.zkp import ZkpHandler

        hs = Mock()
        hs.get_datastores.return_value.main = Mock()
        hs.get_datastores.return_value.main.get_user_did_map_by_user_id = AsyncMock(
            return_value={
                "matrix_user_id": "@alice:test",
                "xrpl_address": "rEXPLICIT111111111111111111111111111",
                "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "did_document_hash": "hash",
                "credential_id": "cred-123",
            }
        )
        hs.get_datastores.return_value.main.upsert_user_did_map = AsyncMock()
        hs.get_clock.return_value.time_msec.return_value = 1234

        zkp_module.rust_zkp = Mock()
        zkp_module.rust_zkp.verify_zkp_binding.return_value = {
            "valid": True,
            "verified_at": 1234,
        }

        handler = ZkpHandler(hs)
        result = asyncio.run(
            handler.verify_e2ee_binding(
                matrix_user_id="@alice:test",
                xrpl_address="rEXPLICIT111111111111111111111111111",
                proof={"type": "groth16"},
                public_signals={
                    "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                    "xrpl_address": "rEXPLICIT111111111111111111111111111",
                    "credential_id": "cred-123",
                    "e2ee_pubkey_commitment": "abc123",
                },
                e2ee_pubkey_commitment="abc123",
            )
        )

        self.assertIn("valid", result)
        hs.get_datastores.return_value.main.upsert_user_did_map.assert_awaited()
