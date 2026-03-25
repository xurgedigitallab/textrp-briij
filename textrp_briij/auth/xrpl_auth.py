#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, TypedDict

from textrp_briij.api.errors import Codes, LoginError, StoreError, SynapseError
from textrp_briij.api.ratelimiting import Ratelimiter
from textrp_briij.auth.wallet_auth_types import (
    WALLET_E2EE_RECOVERY_ACCOUNT_DATA_TYPE,
    WALLET_IDENTITY_ACCOUNT_DATA_TYPE,
    XRPL_WALLET_ACCOUNT_DATA_TYPE,
    build_wallet_identity_payload,
)
from textrp_briij.auth.wallet_recovery_envelope import validate_wallet_recovery_envelope
from textrp_briij.auth.xrpl_chain_adapter import XrplChainAdapter
from textrp_briij.types import JsonDict, UserID
from textrp_briij.util.stringutils import random_string

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer

class XrplChallengeSession(TypedDict):
    address: str
    network: str
    challenge: str
    nonce: str
    issued_at_ms: int
    preferred_localpart: str | None
    display_name: str | None

class XrplAuth:
    LOGIN_TYPE = "io.briij.login.xrpl"
    SESSION_TYPE = "xrpl_auth"
    SUPPORTED_NETWORKS = ("xrpl", "xahau")

    def __init__(self, hs: "HomeServer"):
        self._hs = hs
        self._store = hs.get_datastores().main
        self._clock = hs.get_clock()
        self._adapter = XrplChainAdapter()
        self._auth_handler = hs.get_auth_handler()
        self._registration_handler = hs.get_registration_handler()
        self._account_data_handler = hs.get_account_data_handler()
        self._config = hs.config.xrpl_auth
        self._wallet_ratelimiter = Ratelimiter(
            store=self._store,
            clock=self._clock,
            cfg=hs.config.ratelimiting.rc_login_account,
        )

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def get_login_type(self) -> str:
        return self._adapter.login_type()

    def is_initial_request(self, login_submission: JsonDict) -> bool:
        return self._adapter.is_initial_request(login_submission)

    async def issue_challenge(
        self,
        address: Any,
        network: Any,
        preferred_localpart: Any = None,
        username: Any = None,
        display_name: Any = None,
    ) -> JsonDict:
        normalized_address = self._adapter.validate_account_id(address)
        normalized_network = self._adapter.validate_network(network)
        normalized_localpart = self._resolve_requested_localpart(
            preferred_localpart,
            username,
        )
        normalized_display_name = self._normalize_display_name(display_name)
        await self._wallet_ratelimiter.ratelimit(
            None,
            (normalized_network, normalized_address),
        )
        challenge_session = self._build_challenge_session(
            normalized_address,
            normalized_network,
            normalized_localpart,
            normalized_display_name,
        )
        session_id = await self._store.create_session(
            self._adapter.session_type(),
            challenge_session,
            self._config.challenge_ttl_ms,
        )
        return {
            "session": session_id,
            "challenge": challenge_session["challenge"],
        }

    async def complete_auth(self, login_submission: JsonDict) -> str:
        session_id = login_submission.get("session")
        address = login_submission.get("address")
        signature = login_submission.get("signature")
        public_key = login_submission.get("public_key")
        network = login_submission.get("network")

        if not isinstance(session_id, str) or not session_id:
            raise SynapseError(400, "Missing session", Codes.MISSING_PARAM)
        if not isinstance(signature, str) or not signature:
            raise SynapseError(400, "Missing signature", Codes.MISSING_PARAM)
        if public_key is not None and not isinstance(public_key, str):
            raise SynapseError(400, "Invalid public_key", Codes.INVALID_PARAM)

        normalized_address = self._adapter.validate_account_id(address)
        challenge_session = await self._consume_challenge_session(session_id)
        self._validate_consumed_session(
            challenge_session,
            normalized_address,
            network,
        )

        wallet_link = await self._store.get_wallet_link_by_address(
            normalized_address,
            challenge_session["network"],
        )

        resolved_public_key: str | None = public_key or (
            wallet_link.get("public_key") if wallet_link is not None else None
        )

        resolved_public_key = self._adapter.verify_login_proof(
            account_id=normalized_address,
            challenge=challenge_session["challenge"],
            signature=signature,
            public_key=resolved_public_key,
        )

        if wallet_link is not None:
            user_id = wallet_link["user_id"]
            self._validate_existing_wallet_link_preferences(user_id, challenge_session)
        else:
            if not self._config.allow_account_creation:
                raise LoginError(
                    403,
                    "This wallet is not linked to a Matrix account",
                    errcode=Codes.FORBIDDEN,
                )
            user_id = await self._register_wallet_user(
                normalized_address,
                challenge_session["network"],
                challenge_session["preferred_localpart"],
                challenge_session["display_name"],
            )

        await self._store.upsert_wallet_link(
            user_id,
            normalized_address,
            challenge_session["network"],
            resolved_public_key,
            self._clock.time_msec(),
        )
        await self._account_data_handler.add_account_data_for_user(
            user_id,
            XRPL_WALLET_ACCOUNT_DATA_TYPE,
            {
                "address": normalized_address,
                "network": challenge_session["network"],
                "public_key": resolved_public_key,
            },
        )
        await self._account_data_handler.add_account_data_for_user(
            user_id,
            WALLET_IDENTITY_ACCOUNT_DATA_TYPE,
            build_wallet_identity_payload(
                chain_id=self._adapter.chain_id(),
                account_id=normalized_address,
                public_key=resolved_public_key,
                network=challenge_session["network"],
            ),
        )
        if "wallet_e2ee_recovery" in login_submission:
            envelope = validate_wallet_recovery_envelope(
                login_submission.get("wallet_e2ee_recovery"),
                expected_chain_id=self._adapter.chain_id(),
                expected_account_id=normalized_address,
            )
            await self._account_data_handler.add_account_data_for_user(
                user_id,
                WALLET_E2EE_RECOVERY_ACCOUNT_DATA_TYPE,
                envelope,
            )
        return user_id

    def _build_challenge_session(
        self,
        address: str,
        network: str,
        preferred_localpart: str | None,
        display_name: str | None,
    ) -> XrplChallengeSession:
        issued_at_ms = self._clock.time_msec()
        nonce = random_string(32)
        challenge = self._adapter.build_challenge(
            address,
            issued_at_ms=issued_at_ms,
            nonce=nonce,
        )
        return {
            "address": address,
            "network": network,
            "challenge": challenge,
            "nonce": nonce,
            "issued_at_ms": issued_at_ms,
            "preferred_localpart": preferred_localpart,
            "display_name": display_name,
        }

    async def _consume_challenge_session(self, session_id: str) -> XrplChallengeSession:
        try:
            session = await self._store.consume_session(
                self._adapter.session_type(),
                session_id,
            )
        except StoreError:
            raise LoginError(
                403,
                "Invalid or expired XRPL login session",
                errcode=Codes.FORBIDDEN,
            )

        if not isinstance(session, dict):
            raise SynapseError(500, "Invalid XRPL login session data")

        address = session.get("address")
        network = session.get("network")
        challenge = session.get("challenge")
        nonce = session.get("nonce")
        issued_at_ms = session.get("issued_at_ms")
        preferred_localpart = session.get("preferred_localpart")
        display_name = session.get("display_name")
        if (
            not isinstance(address, str)
            or not isinstance(network, str)
            or not isinstance(challenge, str)
            or not isinstance(nonce, str)
            or not isinstance(issued_at_ms, int)
            or (
                preferred_localpart is not None
                and not isinstance(preferred_localpart, str)
            )
            or (display_name is not None and not isinstance(display_name, str))
        ):
            raise SynapseError(500, "Invalid XRPL login session payload")

        return {
            "address": address,
            "network": network,
            "challenge": challenge,
            "nonce": nonce,
            "issued_at_ms": issued_at_ms,
            "preferred_localpart": preferred_localpart,
            "display_name": display_name,
        }

    def _validate_consumed_session(
        self,
        challenge_session: XrplChallengeSession,
        address: str,
        network: Any,
    ) -> None:
        normalized_network = (
            challenge_session["network"]
            if network is None
            else self._adapter.validate_network(network)
        )
        if challenge_session["address"] != address:
            raise LoginError(
                403,
                "XRPL login address does not match the issued challenge",
                errcode=Codes.FORBIDDEN,
            )
        if challenge_session["network"] != normalized_network:
            raise LoginError(
                403,
                "XRPL login network does not match the issued challenge",
                errcode=Codes.FORBIDDEN,
            )

        now_ms = self._clock.time_msec()
        if challenge_session["issued_at_ms"] + self._config.challenge_ttl_ms < now_ms:
            raise LoginError(
                403,
                "XRPL login challenge has expired",
                errcode=Codes.FORBIDDEN,
            )

        expected_nonce_marker = f"nonce:{challenge_session['nonce']}"
        if expected_nonce_marker not in challenge_session["challenge"]:
            raise SynapseError(500, "XRPL login challenge is malformed")

    async def _register_wallet_user(
        self,
        address: str,
        network: str,
        preferred_localpart: str | None,
        display_name: str | None,
    ) -> str:
        localpart = await self._allocate_preferred_localpart(preferred_localpart)
        if localpart is None:
            base_localpart = self._sanitize_localpart(f"wallet_{network}_{address[-12:]}")
            localpart = await self._allocate_localpart(base_localpart)
        return await self._registration_handler.register_user(
            localpart=localpart,
            default_display_name=display_name,
        )

    async def _allocate_preferred_localpart(
        self,
        preferred_localpart: str | None,
    ) -> str | None:
        if preferred_localpart is None:
            return None
        await self._registration_handler.check_username(preferred_localpart)
        return preferred_localpart

    async def _allocate_localpart(self, base_localpart: str) -> str:
        if await self._is_localpart_available(base_localpart):
            return base_localpart

        for suffix in range(2, 100):
            candidate = f"{base_localpart}_{suffix}"
            if await self._is_localpart_available(candidate):
                return candidate

        raise SynapseError(500, "Unable to allocate an XRPL-backed Matrix user ID")

    async def _is_localpart_available(self, localpart: str) -> bool:
        user_id = UserID(localpart, self._hs.hostname).to_string()
        existing = await self._auth_handler.check_user_exists(user_id)
        return existing is None

    def _sanitize_localpart(self, value: str) -> str:
        sanitized = re.sub(r"[^a-z0-9._=-]", "_", value.lower()).strip("_")
        if not sanitized:
            raise SynapseError(500, "Unable to derive XRPL-backed Matrix user ID")
        return sanitized

    def _normalize_preferred_localpart(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise SynapseError(400, "Invalid preferred_localpart", Codes.INVALID_PARAM)
        trimmed = value.strip()
        if not trimmed:
            raise SynapseError(400, "Invalid preferred_localpart", Codes.INVALID_PARAM)
        return self._sanitize_localpart(trimmed)

    def _resolve_requested_localpart(
        self,
        preferred_localpart: Any,
        username: Any,
    ) -> str | None:
        normalized_preferred = self._normalize_preferred_localpart(preferred_localpart)
        normalized_username = self._normalize_preferred_localpart(username)

        if (
            normalized_preferred is not None
            and normalized_username is not None
            and normalized_preferred != normalized_username
        ):
            raise SynapseError(
                400,
                "preferred_localpart and username must match when both are provided",
                Codes.INVALID_PARAM,
            )

        return normalized_preferred or normalized_username

    def _normalize_display_name(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise SynapseError(400, "Invalid display_name", Codes.INVALID_PARAM)
        trimmed = value.strip()
        return trimmed or None

    def _validate_existing_wallet_link_preferences(
        self,
        user_id: str,
        challenge_session: XrplChallengeSession,
    ) -> None:
        preferred_localpart = challenge_session["preferred_localpart"]
        if preferred_localpart is None:
            return

        linked_localpart = UserID.from_string(user_id).localpart
        if linked_localpart != preferred_localpart:
            raise LoginError(
                403,
                (
                    f"This wallet is already linked to {user_id}; "
                    "requested username does not match."
                ),
                Codes.FORBIDDEN,
            )
