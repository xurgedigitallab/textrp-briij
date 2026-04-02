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
from textrp_briij.rest.client import did, login, register
from textrp_briij.server import HomeServer
from textrp_briij.util.clock import Clock

from tests import unittest


class DidResolveRestTestCase(unittest.HomeserverTestCase):
    servlets = [
        textrp_briij.rest.admin.register_servlets_for_client_rest_resource,
        login.register_servlets,
        register.register_servlets,
        did.register_servlets,
    ]

    def make_homeserver(self, reactor: MemoryReactor, clock: Clock) -> HomeServer:
        return self.setup_test_homeserver()

    def prepare(self, reactor: MemoryReactor, clock: Clock, hs: HomeServer) -> None:
        self.localpart = "did_resolve_user"
        self.password = "pass"
        self.register_user(self.localpart, self.password)
        self.token = self.login(self.localpart, self.password)

    def test_auth_required(self) -> None:
        channel = self.make_request(
            "GET",
            "/_matrix/client/v3/did/resolve?account=rEXPLICIT111111111111111111111111111",
        )
        self.assertEqual(channel.code, 401)

    def test_resolve_explicit_document(self) -> None:
        channel = self.make_request(
            "GET",
            "/_matrix/client/v3/did/resolve?account=rEXPLICIT111111111111111111111111111",
            access_token=self.token,
        )
        self.assertEqual(channel.code, 200, channel.result)
        self.assertEqual(channel.json_body["resolution_type"], "explicit")
        self.assertIn("did_document", channel.json_body)

    def test_resolve_implicit_document(self) -> None:
        channel = self.make_request(
            "GET",
            "/_matrix/client/v3/did/resolve?account=rImplicit111111111111111111111111111",
            access_token=self.token,
        )
        self.assertEqual(channel.code, 200, channel.result)
        self.assertEqual(channel.json_body["resolution_type"], "implicit")

    def test_missing_account_param(self) -> None:
        channel = self.make_request(
            "GET",
            "/_matrix/client/v3/did/resolve",
            access_token=self.token,
        )
        self.assertEqual(channel.code, 400, channel.result)

    def test_did_resolve_rate_limited_by_ip(self) -> None:
        for _ in range(5):
            ok = self.make_request(
                "GET",
                "/_matrix/client/v3/did/resolve?account=rEXPLICIT111111111111111111111111111",
                access_token=self.token,
            )
            self.assertEqual(ok.code, 200, ok.result)

        limited = self.make_request(
            "GET",
            "/_matrix/client/v3/did/resolve?account=rEXPLICIT111111111111111111111111111",
            access_token=self.token,
        )
        self.assertEqual(limited.code, 429, limited.result)
