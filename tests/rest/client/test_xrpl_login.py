#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

from http import HTTPStatus
from typing import Any, cast

from xrpl.constants import CryptoAlgorithm
from xrpl.core.keypairs import (
    derive_classic_address,
    derive_keypair,
    generate_seed,
    sign,
)

import textrp_briij.rest.admin
from textrp_briij.auth.xrpl_auth import XrplAuth
from textrp_briij.rest.client import login, register
from textrp_briij.rest.client.account import WhoamiRestServlet
from textrp_briij.server import HomeServer

from tests.unittest import HomeserverTestCase, override_config

LOGIN_URL = "/_matrix/client/r0/login"
WHOAMI_URL = "/_matrix/client/r0/account/whoami"


class XrplLoginTestCase(HomeserverTestCase):
    servlets = [
        textrp_briij.rest.admin.register_servlets_for_client_rest_resource,
        login.register_servlets,
        register.register_servlets,
        lambda hs, http_server: WhoamiRestServlet(hs).register(http_server),
    ]

    def make_homeserver(self, reactor, clock) -> HomeServer:  # type: ignore[no-untyped-def]
        hs = self.setup_test_homeserver()
        hs.config.registration.enable_registration = True
        hs.config.registration.registrations_require_3pid = []
        hs.config.registration.auto_join_rooms = []
        hs.config.captcha.enable_registration_captcha = False
        return hs

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_login_flows_advertise_xrpl_login(self) -> None:
        channel = self.make_request("GET", LOGIN_URL)

        self.assertEqual(channel.code, HTTPStatus.OK, channel.result)
        self.assertIn(
            {"type": XrplAuth.LOGIN_TYPE},
            channel.json_body["flows"],
        )

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_initial_request_returns_challenge(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)

        channel = self._start_login(wallet["address"], "xrpl")

        self.assertEqual(channel.code, HTTPStatus.UNAUTHORIZED, channel.result)
        self.assertIn("session", channel.json_body)
        self.assertRegex(
            channel.json_body["challenge"],
            rf"^textrp-briij\|.+Z\|nonce:[A-Za-z]{{32}}\|{wallet['address']}$",
        )

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_successful_xrpl_login_creates_account_and_allows_whoami(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(wallet["address"], "xrpl")
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
        )

        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)
        self.assertIn("access_token", login_response.json_body)
        self.assertTrue(login_response.json_body["user_id"].startswith("@wallet_xrpl_"))

        whoami = self.make_request(
            "GET",
            WHOAMI_URL,
            access_token=login_response.json_body["access_token"],
        )
        self.assertEqual(whoami.code, HTTPStatus.OK, whoami.result)
        self.assertEqual(whoami.json_body["user_id"], login_response.json_body["user_id"])

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_existing_link_can_login_without_public_key(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)

        first_challenge = self._start_login(wallet["address"], "xrpl")
        first_login = self._complete_login(
            wallet,
            cast(str, first_challenge.json_body["session"]),
            cast(str, first_challenge.json_body["challenge"]),
        )
        self.assertEqual(first_login.code, HTTPStatus.OK, first_login.result)

        second_challenge = self._start_login(wallet["address"], "xrpl")
        second_login = self._complete_login(
            wallet,
            cast(str, second_challenge.json_body["session"]),
            cast(str, second_challenge.json_body["challenge"]),
            include_public_key=False,
        )
        self.assertEqual(second_login.code, HTTPStatus.OK, second_login.result)
        self.assertEqual(second_login.json_body["user_id"], first_login.json_body["user_id"])

    @override_config({"xrpl_auth": {"enabled": True, "allow_account_creation": False}})
    def test_unlinked_wallet_rejected_when_account_creation_disabled(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)

        challenge_response = self._start_login(wallet["address"], "xrpl")
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
        )

        self.assertEqual(login_response.code, HTTPStatus.FORBIDDEN, login_response.result)

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_invalid_signature_consumes_session(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(wallet["address"], "xrpl")
        session = cast(str, challenge_response.json_body["session"])
        challenge = cast(str, challenge_response.json_body["challenge"])

        invalid_signature = wallet["signature_for"](challenge[:-1] + "x")
        invalid_attempt = self.make_request(
            "POST",
            LOGIN_URL,
            {
                "type": XrplAuth.LOGIN_TYPE,
                "session": session,
                "address": wallet["address"],
                "signature": invalid_signature,
                "public_key": wallet["public_key"],
            },
        )
        self.assertEqual(invalid_attempt.code, HTTPStatus.FORBIDDEN, invalid_attempt.result)

        replay_attempt = self._complete_login(wallet, session, challenge)
        self.assertEqual(replay_attempt.code, HTTPStatus.FORBIDDEN, replay_attempt.result)

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_xahau_login_with_secp256k1_wallet(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.SECP256K1)
        challenge_response = self._start_login(wallet["address"], "xahau")
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
        )

        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)

    def _start_login(self, address: str, network: str):
        channel = self.make_request(
            "POST",
            LOGIN_URL,
            {
                "type": XrplAuth.LOGIN_TYPE,
                "address": address,
                "network": network,
            },
        )
        return channel

    def _complete_login(
        self,
        wallet: dict[str, Any],
        session: str,
        challenge: str,
        *,
        include_public_key: bool = True,
    ):
        body: dict[str, Any] = {
            "type": XrplAuth.LOGIN_TYPE,
            "session": session,
            "address": wallet["address"],
            "signature": wallet["signature_for"](challenge),
        }
        if include_public_key:
            body["public_key"] = wallet["public_key"]

        return self.make_request("POST", LOGIN_URL, body)

    def _generate_wallet(self, algorithm: CryptoAlgorithm) -> dict[str, Any]:
        seed = generate_seed(algorithm=algorithm)
        public_key, private_key = derive_keypair(seed)
        address = derive_classic_address(public_key)

        def signature_for(message: str) -> str:
            return sign(message.encode("utf-8"), private_key)

        return {
            "seed": seed,
            "public_key": public_key,
            "private_key": private_key,
            "address": address,
            "signature_for": signature_for,
        }
