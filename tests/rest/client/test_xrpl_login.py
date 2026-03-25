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
from textrp_briij.api.errors import Codes
from textrp_briij.auth.xrpl_auth import XrplAuth
from textrp_briij.auth.wallet_auth_types import (
    WALLET_E2EE_RECOVERY_ACCOUNT_DATA_TYPE,
    WALLET_IDENTITY_ACCOUNT_DATA_TYPE,
)
from textrp_briij.rest.client import login, register
from textrp_briij.rest.client.account import WhoamiRestServlet
from textrp_briij.server import HomeServer
from textrp_briij.types import UserID

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
        identity = self.get_success(
            self.hs.get_datastores().main.get_global_account_data_by_type_for_user(
                login_response.json_body["user_id"],
                WALLET_IDENTITY_ACCOUNT_DATA_TYPE,
            )
        )
        self.assertIsNotNone(identity)
        self.assertEqual(identity.get("chain_id"), "xrpl")
        self.assertEqual(identity.get("account_id"), wallet["address"])

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_complete_login_stores_wallet_recovery_envelope(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(wallet["address"], "xrpl")
        envelope = {
            "envelope_version": 1,
            "chain_id": "xrpl",
            "account_id": wallet["address"],
            "created_at_ms": 1,
            "key_id": "wallet-key-1",
            "wallet_wrap": {
                "alg": "xchacha20poly1305",
                "kdf": "blake3",
                "salt": "AA==",
                "nonce": "AA==",
                "ciphertext": "AA==",
            },
            "password_wrap": {
                "alg": "xchacha20poly1305",
                "kdf": "argon2id",
                "salt": "AA==",
                "nonce": "AA==",
                "ciphertext": "AA==",
                "params": {"m": 65536, "t": 3, "p": 1},
            },
        }
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
            wallet_e2ee_recovery=envelope,
        )
        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)
        stored = self.get_success(
            self.hs.get_datastores().main.get_global_account_data_by_type_for_user(
                login_response.json_body["user_id"],
                WALLET_E2EE_RECOVERY_ACCOUNT_DATA_TYPE,
            )
        )
        self.assertIsNotNone(stored)
        self.assertEqual(stored.get("chain_id"), "xrpl")
        self.assertEqual(stored.get("account_id"), wallet["address"])

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_complete_login_rejects_invalid_wallet_recovery_envelope(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(wallet["address"], "xrpl")
        invalid_envelope = {
            "envelope_version": 2,
            "chain_id": "xrpl",
            "account_id": wallet["address"],
            "created_at_ms": 1,
            "key_id": "k",
            "wallet_wrap": {
                "alg": "x",
                "kdf": "x",
                "salt": "AA==",
                "nonce": "AA==",
                "ciphertext": "AA==",
            },
            "password_wrap": {
                "alg": "x",
                "kdf": "x",
                "salt": "AA==",
                "nonce": "AA==",
                "ciphertext": "AA==",
            },
        }
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
            wallet_e2ee_recovery=invalid_envelope,
        )
        self.assertEqual(login_response.code, HTTPStatus.BAD_REQUEST, login_response.result)
        self.assertEqual(login_response.json_body.get("errcode"), Codes.INVALID_PARAM)

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

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_first_login_uses_requested_localpart_and_display_name(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(
            wallet["address"],
            "xrpl",
            preferred_localpart="alice_wallet",
            display_name="Alice",
        )
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
        )

        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)
        self.assertEqual(
            login_response.json_body["user_id"],
            f"@alice_wallet:{self.hs.hostname}",
        )
        display_name = self.get_success(
            self.hs.get_datastores().main.get_profile_displayname(
                UserID.from_string(login_response.json_body["user_id"])
            )
        )
        self.assertEqual(display_name, "Alice")

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_requested_localpart_rejected_when_taken(self) -> None:
        self.register_user("taken", "pass")
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(
            wallet["address"],
            "xrpl",
            preferred_localpart="taken",
            display_name="Taken Fallback",
        )
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
        )

        self.assertEqual(login_response.code, HTTPStatus.BAD_REQUEST, login_response.result)
        self.assertEqual(login_response.json_body.get("errcode"), Codes.USER_IN_USE)

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_initial_request_rejects_invalid_preferred_localpart_type(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        channel = self.make_request(
            "POST",
            LOGIN_URL,
            {
                "type": XrplAuth.LOGIN_TYPE,
                "address": wallet["address"],
                "network": "xrpl",
                "preferred_localpart": 123,
            },
        )
        self.assertEqual(channel.code, HTTPStatus.BAD_REQUEST, channel.result)

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_first_login_accepts_username_alias_for_localpart(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(
            wallet["address"],
            "xrpl",
            username="alias_user",
        )
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
        )

        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)
        self.assertEqual(
            login_response.json_body["user_id"],
            f"@alias_user:{self.hs.hostname}",
        )

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_initial_request_rejects_conflicting_username_and_preferred_localpart(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        channel = self._start_login(
            wallet["address"],
            "xrpl",
            preferred_localpart="alice",
            username="bob",
        )

        self.assertEqual(channel.code, HTTPStatus.BAD_REQUEST, channel.result)
        self.assertEqual(channel.json_body.get("errcode"), Codes.INVALID_PARAM)

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_linked_wallet_rejects_different_requested_localpart(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(
            wallet["address"],
            "xrpl",
            preferred_localpart="first_user",
        )
        first_login = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
        )
        self.assertEqual(first_login.code, HTTPStatus.OK, first_login.result)

        second_challenge = self._start_login(
            wallet["address"],
            "xrpl",
            preferred_localpart="other_user",
        )
        second_login = self._complete_login(
            wallet,
            cast(str, second_challenge.json_body["session"]),
            cast(str, second_challenge.json_body["challenge"]),
        )
        self.assertEqual(second_login.code, HTTPStatus.FORBIDDEN, second_login.result)
        self.assertEqual(second_login.json_body.get("errcode"), Codes.FORBIDDEN)

    def _start_login(
        self,
        address: str,
        network: str,
        *,
        preferred_localpart: str | None = None,
        username: str | None = None,
        display_name: str | None = None,
    ):
        body: dict[str, Any] = {
            "type": XrplAuth.LOGIN_TYPE,
            "address": address,
            "network": network,
        }
        if preferred_localpart is not None:
            body["preferred_localpart"] = preferred_localpart
        if username is not None:
            body["username"] = username
        if display_name is not None:
            body["display_name"] = display_name
        channel = self.make_request(
            "POST",
            LOGIN_URL,
            body,
        )
        return channel

    def _complete_login(
        self,
        wallet: dict[str, Any],
        session: str,
        challenge: str,
        *,
        include_public_key: bool = True,
        wallet_e2ee_recovery: dict[str, Any] | None = None,
    ):
        body: dict[str, Any] = {
            "type": XrplAuth.LOGIN_TYPE,
            "session": session,
            "address": wallet["address"],
            "signature": wallet["signature_for"](challenge),
        }
        if include_public_key:
            body["public_key"] = wallet["public_key"]
        if wallet_e2ee_recovery is not None:
            body["wallet_e2ee_recovery"] = wallet_e2ee_recovery

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
