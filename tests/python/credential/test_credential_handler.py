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


class CredentialHandlerTestCase(unittest.TestCase):
    def test_issue_credential_updates_store(self) -> None:
        from textrp_briij.handlers.credential import CredentialHandler

        hs = Mock()
        hs.get_datastores.return_value.main = Mock()
        hs.get_datastores.return_value.main.get_user_did_map_by_user_id = AsyncMock(
            return_value={
                "matrix_user_id": "@alice:test",
                "xrpl_address": "rEXPLICIT111111111111111111111111111",
                "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "did_document_hash": "hash",
            }
        )
        hs.get_datastores.return_value.main.upsert_user_did_map = AsyncMock()
        hs.get_clock.return_value.time_msec.return_value = 111
        hs.config.ratelimiting.rc_login_account = Mock()
        hs.get_did_handler.return_value = Mock()
        hs.get_did_handler.return_value.resolve_did_document = AsyncMock(
            return_value={"did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111"}
        )

        handler = CredentialHandler(hs)
        handler._credential_ratelimiter.ratelimit = AsyncMock()
        result = asyncio.run(
            handler.issue_login_credential(
                matrix_user_id="@alice:test",
                xrpl_address="rEXPLICIT111111111111111111111111111",
                e2ee_pubkey_commitment="abc123",
            )
        )

        self.assertIn("credential_id", result)
        hs.get_datastores.return_value.main.upsert_user_did_map.assert_awaited()

    def test_duplicate_credential_short_circuit(self) -> None:
        from textrp_briij.handlers.credential import CredentialHandler

        hs = Mock()
        hs.get_datastores.return_value.main = Mock()
        hs.get_datastores.return_value.main.get_user_did_map_by_user_id = AsyncMock(
            return_value={
                "matrix_user_id": "@alice:test",
                "xrpl_address": "rEXPLICIT111111111111111111111111111",
                "did_uri": "did:xrpl:testnet:rEXPLICIT111111111111111111111111111",
                "did_document_hash": "hash",
                "credential_id": "cred-existing",
                "credential_issued_at": 111,
            }
        )
        hs.get_datastores.return_value.main.upsert_user_did_map = AsyncMock()
        hs.get_clock.return_value.time_msec.return_value = 111
        hs.config.ratelimiting.rc_login_account = Mock()
        hs.get_did_handler.return_value = Mock()

        handler = CredentialHandler(hs)
        handler._credential_ratelimiter.ratelimit = AsyncMock()
        result = asyncio.run(
            handler.issue_login_credential(
                matrix_user_id="@alice:test",
                xrpl_address="rEXPLICIT111111111111111111111111111",
                e2ee_pubkey_commitment="abc123",
            )
        )
        self.assertEqual(result["credential_id"], "cred-existing")
        self.assertTrue(result["duplicate"])
