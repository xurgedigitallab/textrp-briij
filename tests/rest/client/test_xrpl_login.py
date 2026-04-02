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
from textrp_briij.storage.engines import PostgresEngine
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
        if isinstance(self.hs.get_datastores().main.database_engine, PostgresEngine):
            did_mapping = self.get_success(
                self.hs.get_datastores().main.get_user_did_map_by_user_id(
                    login_response.json_body["user_id"]
                )
            )
            self.assertIsNotNone(did_mapping)
            assert did_mapping is not None
            self.assertEqual(did_mapping["xrpl_address"], wallet["address"])
            self.assertTrue(did_mapping["did_uri"].startswith("did:xrpl:testnet:"))

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
        self.assertIn(
            "retry without username",
            login_response.json_body.get("error", ""),
        )

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

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_successful_login_triggers_credential_issue(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        calls: list[tuple[str, str, str]] = []

        async def _issue_credential(
            matrix_user_id: str, xrpl_address: str, e2ee_pubkey_commitment: str
        ) -> dict[str, str]:
            calls.append((matrix_user_id, xrpl_address, e2ee_pubkey_commitment))
            return {"credential_id": "cred-test"}

        self.hs.get_credential_handler().issue_login_credential = _issue_credential  # type: ignore[method-assign]

        challenge_response = self._start_login(wallet["address"], "xrpl")
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
        )
        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], wallet["address"])

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_successful_login_accepts_optional_zkp_payload(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        zkp_calls: list[tuple[str, str, str]] = []

        async def _verify_zkp(
            matrix_user_id: str,
            xrpl_address: str,
            proof: dict[str, Any],
            public_signals: dict[str, Any],
            e2ee_pubkey_commitment: str,
        ) -> dict[str, Any]:
            zkp_calls.append((matrix_user_id, xrpl_address, e2ee_pubkey_commitment))
            return {"valid": True, "verified_at": 123}

        self.hs.get_zkp_handler().verify_e2ee_binding = _verify_zkp  # type: ignore[method-assign]

        challenge_response = self._start_login(wallet["address"], "xrpl")
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
            zkp_payload={
                "proof": {"type": "groth16"},
                "public_signals": {
                    "did_uri": f"did:xrpl:testnet:{wallet['address']}",
                    "xrpl_address": wallet["address"],
                    "credential_id": "cred-test",
                    "e2ee_pubkey_commitment": "abc123",
                },
                "e2ee_pubkey_commitment": "abc123",
            },
        )
        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)
        self.assertEqual(len(zkp_calls), 1)

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_full_flow_sequence_wallet_did_credential_zkp(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        call_order: list[str] = []

        async def _commit_did(*args: Any, **kwargs: Any) -> dict[str, Any]:
            call_order.append("did")
            return {"did_uri": f"did:xrpl:testnet:{wallet['address']}"}

        async def _issue_credential(*args: Any, **kwargs: Any) -> dict[str, Any]:
            call_order.append("credential")
            return {"credential_id": "cred-seq", "status": "issued"}

        async def _verify_zkp(*args: Any, **kwargs: Any) -> dict[str, Any]:
            call_order.append("zkp")
            return {"valid": True, "verified_at": 123}

        self.hs.get_did_handler().commit_wallet_did_binding = _commit_did  # type: ignore[method-assign]
        self.hs.get_credential_handler().issue_login_credential = _issue_credential  # type: ignore[method-assign]
        self.hs.get_zkp_handler().verify_e2ee_binding = _verify_zkp  # type: ignore[method-assign]

        challenge_response = self._start_login(wallet["address"], "xrpl")
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
            zkp_payload={
                "proof": {"type": "groth16"},
                "public_signals": {
                    "did_uri": f"did:xrpl:testnet:{wallet['address']}",
                    "xrpl_address": wallet["address"],
                    "credential_id": "cred-seq",
                    "e2ee_pubkey_commitment": "abc123",
                },
                "e2ee_pubkey_commitment": "abc123",
            },
        )
        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)
        self.assertEqual(call_order, ["did", "credential", "zkp"])
        self.assertIn("device_id", login_response.json_body)

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_login_with_zkp_declined_falls_back_to_signature_path(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        zkp_calls: list[str] = []

        async def _verify_zkp(*args: Any, **kwargs: Any) -> dict[str, Any]:
            zkp_calls.append("called")
            return {"valid": True}

        self.hs.get_zkp_handler().verify_e2ee_binding = _verify_zkp  # type: ignore[method-assign]

        challenge_response = self._start_login(wallet["address"], "xrpl")
        login_response = self._complete_login(
            wallet,
            cast(str, challenge_response.json_body["session"]),
            cast(str, challenge_response.json_body["challenge"]),
            zkp_declined=True,
        )
        self.assertEqual(login_response.code, HTTPStatus.OK, login_response.result)
        self.assertEqual(zkp_calls, [])

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_conflict_response_includes_recovery_suggestion(self) -> None:
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
        self.assertIn("Try logging in without username", second_login.json_body.get("error", ""))

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_rejects_secret_material_in_login_payload(self) -> None:
        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        challenge_response = self._start_login(wallet["address"], "xrpl")
        login_response = self.make_request(
            "POST",
            LOGIN_URL,
            {
                "type": XrplAuth.LOGIN_TYPE,
                "session": cast(str, challenge_response.json_body["session"]),
                "address": wallet["address"],
                "signature": wallet["signature_for"](cast(str, challenge_response.json_body["challenge"])),
                "public_key": wallet["public_key"],
                "private_key": wallet["private_key"],
            },
        )
        self.assertEqual(login_response.code, HTTPStatus.BAD_REQUEST, login_response.result)

    @override_config({"xrpl_auth": {"enabled": True}})
    def test_xrpl_login_rate_limited_by_ip(self) -> None:
        for _ in range(5):
            wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
            challenge = self._start_login(wallet["address"], "xrpl")
            self.assertEqual(challenge.code, HTTPStatus.UNAUTHORIZED, challenge.result)

        wallet = self._generate_wallet(CryptoAlgorithm.ED25519)
        limited = self._start_login(wallet["address"], "xrpl")
        self.assertEqual(limited.code, HTTPStatus.TOO_MANY_REQUESTS, limited.result)

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
        zkp_payload: dict[str, Any] | None = None,
        zkp_declined: bool = False,
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
        if zkp_payload is not None:
            body["zkp_proof"] = zkp_payload["proof"]
            body["zkp_public_signals"] = zkp_payload["public_signals"]
            body["e2ee_pubkey_commitment"] = zkp_payload["e2ee_pubkey_commitment"]
        if zkp_declined:
            body["zkp_declined"] = True

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
