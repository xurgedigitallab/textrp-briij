#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import xrpl.clients as xrpl_clients
from xrpl.asyncio.clients import AsyncJsonRpcClient as XrplAsyncJsonRpcClient
from xrpl.core.keypairs import derive_classic_address, is_valid_message
from xrpl.models.requests import AccountInfo

from textrp_briij.api.errors import Codes
from textrp_briij.module_api import ModuleApi
from textrp_briij.types import JsonDict

AsyncJsonRpcClient = getattr(
    xrpl_clients, "AsyncJsonRpcClient", XrplAsyncJsonRpcClient
)
logger = logging.getLogger(__name__)


class WalletAuthError(Exception):
    def __init__(self, errcode: Codes, message: str) -> None:
        super().__init__(message)
        self.errcode = errcode
        self.message = message


class WalletProvider:
    LOGIN_TYPE = "io.briij.login.xrpl"
    LOGIN_FIELDS = ("wallet_address", "signature", "challenge", "network")
    SUPPORTED_NETWORKS = ("xrpl", "xahau")
    TABLE_NAME = "briij_wallet_links"
    CHALLENGE_MAX_AGE_MS = 60_000
    RATE_LIMIT_WINDOW_MS = 60_000
    RATE_LIMIT_ATTEMPTS = 10

    def __init__(self, config: JsonDict, api: ModuleApi):
        self.api = api
        self._config = self.parse_config(config)
        self._wallet_table_ready = False
        self.allowed_networks = tuple(
            str(network) for network in self._config["allowed_networks"]
        )
        self.default_network = str(self._config["default_network"])
        self.jsonrpc_urls_by_network = {
            network: tuple(
                str(url)
                for url in self._config[network]["jsonrpc_urls"]  # type: ignore[index]
            )
            for network in self.allowed_networks
        }
        self.clients_by_network = {
            network: AsyncJsonRpcClient(self.jsonrpc_urls_by_network[network][0])
            for network in self.allowed_networks
        }
        self._used_challenge_nonces: dict[str, int] = {}
        # In-memory rate limiter stub; replace with shared storage in production.
        self._wallet_rate_limits: dict[str, tuple[int, int]] = {}
        self._register_callbacks()

    def _register_callbacks(self) -> None:
        self.api.register_password_auth_provider_callbacks(
            auth_checkers={(self.LOGIN_TYPE, self.LOGIN_FIELDS): self.check_auth}
        )

    @staticmethod
    def parse_config(config: JsonDict) -> JsonDict:
        normalized: JsonDict = {}

        allowed_networks_value = config.get("allowed_networks")
        if isinstance(allowed_networks_value, list):
            allowed_networks = [str(network) for network in allowed_networks_value]
        else:
            allowed_networks = ["xrpl", "xahau"]

        default_network_value = config.get("default_network")
        if isinstance(default_network_value, str):
            default_network = default_network_value
        else:
            default_network = "xrpl"

        normalized["allowed_networks"] = allowed_networks
        normalized["default_network"] = default_network

        for network in WalletProvider.SUPPORTED_NETWORKS:
            network_config_value = config.get(network)
            network_config: JsonDict = (
                dict(network_config_value)
                if isinstance(network_config_value, dict)
                else {}
            )

            urls_value = network_config.get("jsonrpc_urls")
            if isinstance(urls_value, list):
                jsonrpc_urls = [str(url) for url in urls_value]
            else:
                fallback_url = network_config.get("jsonrpc_url")
                if isinstance(fallback_url, str):
                    jsonrpc_urls = [fallback_url]
                else:
                    jsonrpc_urls = []

            normalized[network] = {"jsonrpc_urls": jsonrpc_urls}

        return normalized

    def get_supported_login_types(self) -> dict[str, list[str]]:
        return {self.LOGIN_TYPE: list(self.LOGIN_FIELDS)}

    async def _ensure_wallet_links_table(self) -> None:
        if self._wallet_table_ready:
            return

        def _create_wallet_links_table(txn: Any) -> None:
            txn.execute(
                """
                CREATE TABLE IF NOT EXISTS briij_wallet_links (
                    user_id TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    network TEXT NOT NULL,
                    linked_at BIGINT NOT NULL,
                    UNIQUE(wallet_address, network)
                )
                """
            )

        await self.api.run_db_interaction(
            "briij_create_wallet_links_table", _create_wallet_links_table
        )
        self._wallet_table_ready = True

    async def _store_wallet_mapping(
        self, user_id: str, wallet_address: str, network: str
    ) -> None:
        await self._ensure_wallet_links_table()
        linked_at = int(time.time() * 1000)

        def _upsert_wallet_mapping(txn: Any) -> None:
            txn.execute(
                """
                INSERT INTO briij_wallet_links (user_id, wallet_address, network, linked_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (wallet_address, network) DO UPDATE
                SET user_id = excluded.user_id, linked_at = excluded.linked_at
                """,
                (user_id, wallet_address, network, linked_at),
            )

        await self.api.run_db_interaction(
            "briij_store_wallet_mapping", _upsert_wallet_mapping
        )

    async def _get_user_by_wallet(
        self, wallet_address: str, network: str
    ) -> str | None:
        await self._ensure_wallet_links_table()

        def _select_wallet_mapping(txn: Any) -> str | None:
            txn.execute(
                """
                SELECT user_id
                FROM briij_wallet_links
                WHERE wallet_address = ? AND network = ?
                """,
                (wallet_address, network),
            )
            row = txn.fetchone()
            if row is None:
                return None
            return str(row[0])

        return await self.api.run_db_interaction(
            "briij_get_user_by_wallet", _select_wallet_mapping
        )

    async def _is_localpart_available(self, localpart: str) -> bool:
        existing_user_id = await self.api.check_user_exists(
            self.api.get_qualified_user_id(localpart)
        )
        return existing_user_id is None

    def _parse_challenge(self, challenge: Any) -> JsonDict | None:
        if isinstance(challenge, dict):
            return dict(challenge)
        if isinstance(challenge, str):
            try:
                parsed = json.loads(challenge)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed, dict):
                return dict(parsed)
        return None

    def _decode_signature(self, signature: str) -> bytes | None:
        try:
            return bytes.fromhex(signature)
        except ValueError:
            return None

    def _parse_timestamp_ms(self, timestamp: Any) -> int | None:
        if isinstance(timestamp, str):
            if not timestamp.isdigit():
                return None
            parsed = int(timestamp)
        elif isinstance(timestamp, int):
            parsed = timestamp
        elif isinstance(timestamp, float):
            parsed = int(timestamp)
        else:
            return None

        if parsed < 10_000_000_000:
            return parsed * 1000
        return parsed

    def _extract_localpart_from_username(self, username: str) -> str:
        if username.startswith("@") and ":" in username:
            localpart = username[1:].split(":", 1)[0]
        else:
            localpart = username

        sanitized = re.sub(r"[^a-z0-9._=-]", "_", localpart.lower()).strip("_")
        return sanitized

    def _consume_nonce(
        self, network: str, wallet_address: str, nonce: str, timestamp_ms: int
    ) -> bool:
        now_ms = int(time.time() * 1000)
        expired = [
            key
            for key, expires_at in self._used_challenge_nonces.items()
            if expires_at <= now_ms
        ]
        for key in expired:
            del self._used_challenge_nonces[key]

        nonce_key = f"{network}:{wallet_address}:{nonce}"
        if nonce_key in self._used_challenge_nonces:
            return False

        self._used_challenge_nonces[nonce_key] = now_ms + self.CHALLENGE_MAX_AGE_MS
        return True

    def _enforce_nonce_timestamp(
        self, challenge_dict: JsonDict, wallet_address: str, network: str
    ) -> None:
        nonce = challenge_dict.get("nonce")
        if not isinstance(nonce, str) or not nonce:
            raise WalletAuthError(Codes.MISSING_PARAM, "Missing or invalid nonce")

        timestamp_ms = self._parse_timestamp_ms(challenge_dict.get("timestamp"))
        if timestamp_ms is None:
            raise WalletAuthError(Codes.MISSING_PARAM, "Missing or invalid timestamp")

        now_ms = int(time.time() * 1000)
        if timestamp_ms > now_ms:
            raise WalletAuthError(Codes.INVALID_PARAM, "Timestamp is in the future")
        if now_ms - timestamp_ms > self.CHALLENGE_MAX_AGE_MS:
            raise WalletAuthError(Codes.FORBIDDEN, "Challenge has expired")

        if not self._consume_nonce(network, wallet_address, nonce, timestamp_ms):
            raise WalletAuthError(Codes.FORBIDDEN, "Nonce has already been used")

        message = challenge_dict.get("message")
        if isinstance(message, str):
            if nonce not in message or str(timestamp_ms) not in message:
                raise WalletAuthError(
                    Codes.INVALID_PARAM,
                    "Challenge message must include nonce and timestamp",
                )

    def _check_rate_limit(self, wallet_address: str, network: str) -> None:
        key = f"{network}:{wallet_address.lower()}"
        now_ms = int(time.time() * 1000)
        window_start_ms, attempts = self._wallet_rate_limits.get(key, (now_ms, 0))

        if now_ms - window_start_ms > self.RATE_LIMIT_WINDOW_MS:
            window_start_ms = now_ms
            attempts = 0

        attempts += 1
        self._wallet_rate_limits[key] = (window_start_ms, attempts)

        if attempts > self.RATE_LIMIT_ATTEMPTS:
            raise WalletAuthError(
                Codes.LIMIT_EXCEEDED,
                "Too many authentication attempts for this wallet",
            )

    def _clear_rate_limit(self, wallet_address: str, network: str) -> None:
        key = f"{network}:{wallet_address.lower()}"
        self._wallet_rate_limits.pop(key, None)

    async def _verify_xrpl_signature(
        self, wallet_address: str, signature: str, challenge: Any, network: str
    ) -> bool:
        if network not in self.clients_by_network:
            raise WalletAuthError(Codes.INVALID_PARAM, "Unsupported network")

        challenge_dict = self._parse_challenge(challenge)
        if challenge_dict is None:
            raise WalletAuthError(Codes.INVALID_PARAM, "Invalid challenge payload")
        self._enforce_nonce_timestamp(challenge_dict, wallet_address, network)

        public_key = challenge_dict.get("public_key")
        if not isinstance(public_key, str):
            raise WalletAuthError(Codes.MISSING_PARAM, "Missing public_key")

        algorithm = challenge_dict.get("algorithm")
        if isinstance(algorithm, str):
            algo_lc = algorithm.lower()
            if algo_lc == "ed25519" and not public_key.upper().startswith("ED"):
                raise WalletAuthError(Codes.INVALID_PARAM, "Algorithm/public_key mismatch")
            if algo_lc == "secp256k1" and public_key.upper().startswith("ED"):
                raise WalletAuthError(Codes.INVALID_PARAM, "Algorithm/public_key mismatch")

        try:
            derived_address = derive_classic_address(public_key)
        except Exception:
            raise WalletAuthError(Codes.INVALID_PARAM, "Invalid public_key")

        if derived_address != wallet_address:
            raise WalletAuthError(Codes.FORBIDDEN, "Wallet address does not match key")

        message = challenge_dict.get("message")
        if not isinstance(message, str):
            raise WalletAuthError(Codes.MISSING_PARAM, "Missing message in challenge")

        signature_bytes = self._decode_signature(signature)
        if signature_bytes is None:
            raise WalletAuthError(Codes.INVALID_SIGNATURE, "Invalid signature format")

        if not is_valid_message(
            message.encode("utf-8"), signature_bytes, public_key.upper()
        ):
            raise WalletAuthError(Codes.INVALID_SIGNATURE, "Signature verification failed")

        client = self.clients_by_network[network]
        try:
            account_info_response = await client.request(
                AccountInfo(account=wallet_address, ledger_index="validated", strict=True)
            )
        except Exception:
            raise WalletAuthError(Codes.UNKNOWN, "Unable to reach XRPL RPC")

        if not account_info_response.is_successful():
            raise WalletAuthError(Codes.FORBIDDEN, "Wallet account not found on ledger")

        return True

    async def check_auth(
        self, username: str, login_type: str, login_dict: JsonDict
    ) -> Any:
        try:
            if login_type != self.LOGIN_TYPE:
                return None

            wallet_address = login_dict.get("wallet_address")
            signature = login_dict.get("signature")
            challenge = login_dict.get("challenge")
            requested_network = login_dict.get("network", self.default_network)

            if not isinstance(wallet_address, str) or not wallet_address:
                raise WalletAuthError(Codes.MISSING_PARAM, "Missing wallet_address")
            if not isinstance(signature, str) or not signature:
                raise WalletAuthError(Codes.MISSING_PARAM, "Missing signature")
            if challenge is None:
                raise WalletAuthError(Codes.MISSING_PARAM, "Missing challenge")
            if not isinstance(requested_network, str):
                raise WalletAuthError(Codes.INVALID_PARAM, "Invalid network")

            network = requested_network.lower()
            if network not in self.allowed_networks:
                raise WalletAuthError(Codes.INVALID_PARAM, "Unsupported network")

            self._check_rate_limit(wallet_address, network)

            await self._verify_xrpl_signature(
                wallet_address=wallet_address,
                signature=signature,
                challenge=challenge,
                network=network,
            )

            existing_user_id = await self._get_user_by_wallet(wallet_address, network)
            if existing_user_id is not None:
                await self._store_wallet_mapping(existing_user_id, wallet_address, network)
                self._clear_rate_limit(wallet_address, network)
                return (existing_user_id, None)

            preferred_localpart = self._extract_localpart_from_username(username)
            wallet_fallback = f"wallet_{wallet_address[-12:].lower()}"

            candidate_localparts: list[str] = []
            if preferred_localpart:
                candidate_localparts.append(preferred_localpart)
            candidate_localparts.append(wallet_fallback)

            chosen_localpart: str | None = None
            for base_candidate in candidate_localparts:
                if await self._is_localpart_available(base_candidate):
                    chosen_localpart = base_candidate
                    break
                for suffix in range(2, 100):
                    suffixed_candidate = f"{base_candidate}_{suffix}"
                    if await self._is_localpart_available(suffixed_candidate):
                        chosen_localpart = suffixed_candidate
                        break
                if chosen_localpart is not None:
                    break

            if chosen_localpart is None:
                raise WalletAuthError(Codes.INVALID_USERNAME, "Unable to allocate user ID")

            try:
                user_id = await self.api.register_user(localpart=chosen_localpart)
            except Exception:
                qualified_id = self.api.get_qualified_user_id(chosen_localpart)
                existing_registered_id = await self.api.check_user_exists(qualified_id)
                if existing_registered_id is None:
                    raise WalletAuthError(Codes.UNKNOWN, "Failed to create user")
                user_id = existing_registered_id

            await self._store_wallet_mapping(user_id, wallet_address, network)
            self._clear_rate_limit(wallet_address, network)
            return (user_id, None)

        except WalletAuthError as e:
            logger.info("Wallet auth rejected [%s]: %s", e.errcode.value, e.message)
            return None
        except Exception:
            logger.exception("Wallet auth rejected [%s]", Codes.UNKNOWN.value)
            return None
