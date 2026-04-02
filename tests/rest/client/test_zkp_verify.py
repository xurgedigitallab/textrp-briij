#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from twisted.internet.testing import MemoryReactor

import textrp_briij.rest.admin
from textrp_briij.rest.client import login, register, zkp
from textrp_briij.server import HomeServer
from textrp_briij.util.clock import Clock

from tests import unittest


class ZkpVerifyRestTestCase(unittest.HomeserverTestCase):
    servlets = [
        textrp_briij.rest.admin.register_servlets_for_client_rest_resource,
        login.register_servlets,
        register.register_servlets,
        zkp.register_servlets,
    ]

    def make_homeserver(self, reactor: MemoryReactor, clock: Clock) -> HomeServer:
        return self.setup_test_homeserver()

    def prepare(self, reactor: MemoryReactor, clock: Clock, hs: HomeServer) -> None:
        self.localpart = "zkp_verify_user"
        self.password = "pass"
        self.register_user(self.localpart, self.password)
        self.token = self.login(self.localpart, self.password)

        async def _verify_e2ee_binding(**kwargs):
            return {"valid": True, "verified_at": 123}

        hs.get_zkp_handler().verify_e2ee_binding = _verify_e2ee_binding  # type: ignore[method-assign]

    def test_auth_required(self) -> None:
        channel = self.make_request("POST", "/_matrix/client/v3/zkp/verify", {})
        self.assertEqual(channel.code, 401)

    def test_verify_zkp(self) -> None:
        channel = self.make_request(
            "POST",
            "/_matrix/client/v3/zkp/verify",
            {
                "proof": {"type": "groth16"},
                "public_signals": {
                    "xrpl_address": "rEXPLICIT111111111111111111111111111",
                    "e2ee_pubkey_commitment": "abc123",
                },
            },
            access_token=self.token,
        )
        self.assertEqual(channel.code, 200, channel.result)
        self.assertIn("valid", channel.json_body)

    def test_rejects_oversized_proof(self) -> None:
        oversized = {"blob": "a" * (70 * 1024)}
        channel = self.make_request(
            "POST",
            "/_matrix/client/v3/zkp/verify",
            {
                "proof": oversized,
                "public_signals": {
                    "xrpl_address": "rEXPLICIT111111111111111111111111111",
                    "e2ee_pubkey_commitment": "abc123",
                },
            },
            access_token=self.token,
        )
        self.assertEqual(channel.code, 400, channel.result)

    def test_zkp_verify_rate_limited_by_ip(self) -> None:
        payload = {
            "proof": {"type": "groth16"},
            "public_signals": {
                "xrpl_address": "rEXPLICIT111111111111111111111111111",
                "e2ee_pubkey_commitment": "abc123",
            },
        }
        for _ in range(5):
            ok = self.make_request(
                "POST",
                "/_matrix/client/v3/zkp/verify",
                payload,
                access_token=self.token,
            )
            self.assertEqual(ok.code, 200, ok.result)

        limited = self.make_request(
            "POST",
            "/_matrix/client/v3/zkp/verify",
            payload,
            access_token=self.token,
        )
        self.assertEqual(limited.code, 429, limited.result)
