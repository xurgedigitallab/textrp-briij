# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 TextRP https://textrp.io
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote
from urllib.request import urlopen

from xrpl.models.requests import AccountNFTs, Tx
from xrpl.models.transactions import NFTokenModify

from textrp_briij.api.constants import EventTypes, Membership
from textrp_briij.api.errors import Codes, SynapseError
from textrp_briij.events import EventBase
from textrp_briij.types import JsonDict, StateMap, create_requester

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer

logger = logging.getLogger(__name__)

VERIFY_REQUEST_EVENT = "m.user.verify.request"
VERIFY_ACCEPT_EVENT = "m.user.verify.accept"
VERIFIED_EVENT = "m.user.verified"
CHAT_PAY_EVENT = "m.chat.pay"
XRPL_IDENTITY_ACCOUNT_DATA_EVENT = "io.textrp.xrpl.identity_nft"
TRUST_CACHE_NAME = "xrpl_trust"
URI_METADATA_CACHE_NAME = "xrpl_uri_metadata"


class BaseHandler:
    def __init__(self, hs: "HomeServer"):
        self.hs = hs


class VerificationHandler(BaseHandler):
    """Processes XRPL-backed Matrix verification events."""

    def __init__(self, hs: "HomeServer"):
        super().__init__(hs)
        self._store = hs.get_datastores().main
        self._server_name = hs.hostname
        self._is_mine_id = hs.is_mine_id
        self._account_data_handler = hs.get_account_data_handler()
        self._event_creation_handler = hs.get_event_creation_handler()
        self._xrpl_identity_handler = hs.get_xrpl_identity_handler()
        self._external_cache = hs.get_external_cache()

        self._event_handlers = {
            VERIFY_REQUEST_EVENT: self._handle_verify_request,
            VERIFY_ACCEPT_EVENT: self._handle_verify_accept,
        }

        hs.get_module_api_callbacks().third_party_event_rules.register_third_party_rules_callbacks(
            check_event_allowed=self._check_event_allowed,
            on_new_event=self._on_new_event,
        )

    async def _check_event_allowed(
        self,
        event: EventBase,
        state_events: StateMap[EventBase],
    ) -> tuple[bool, dict | None]:
        if event.type != CHAT_PAY_EVENT:
            return True, None

        payer_user_id = event.sender
        payee_user_id = self._extract_payee_user_id(
            event.content,
            state_events,
            payer_user_id,
        )
        if not payee_user_id:
            raise SynapseError(
                403,
                "not_in_trust_network",
                errcode=Codes.FORBIDDEN,
            )

        payer_xrpl = await self._resolve_xrpl_address_for_user(payer_user_id)
        payee_xrpl = await self._resolve_xrpl_address_for_user(payee_user_id)
        if not payer_xrpl or not payee_xrpl:
            raise SynapseError(
                403,
                "not_in_trust_network",
                errcode=Codes.FORBIDDEN,
            )

        trusted = await self.check_trust(payer_xrpl, payee_xrpl)
        if not trusted:
            raise SynapseError(
                403,
                "not_in_trust_network",
                errcode=Codes.FORBIDDEN,
            )

        return True, None

    async def _on_new_event(self, event: EventBase, *_args: Any) -> None:
        handler = self._event_handlers.get(event.type)
        if handler is None:
            return

        if not self._is_mine_id(event.sender):
            return

        try:
            await handler(event)
        except Exception:
            logger.exception("Failed handling XRPL verification event %s", event.event_id)

    async def _handle_verify_request(self, event: EventBase) -> None:
        content = dict(event.content)
        issuer_xrpl_address = str(content.get("issuer_xrpl_address", "")).strip()
        target_xrpl_address = str(content.get("target_xrpl_address", "")).strip()
        if not issuer_xrpl_address or not target_xrpl_address:
            return

        # Ensure both parties have identity NFTs on-ledger before recording request state.
        await self._fetch_identity_nft(issuer_xrpl_address)
        await self._fetch_identity_nft(target_xrpl_address)

        verified_content: JsonDict = {
            "status": "requested",
            "trust_model": "nft_metadata",
            "tx_hash": str(content.get("tx_hash", "")).strip(),
            "requester_user_id": event.sender,
            "issuer_xrpl_address": issuer_xrpl_address,
            "target_xrpl_address": target_xrpl_address,
            "validated": True,
            "transaction_type": "NFTokenModify",
        }

        await self._persist_verified_account_data(event.sender, verified_content)
        await self._notify_rooms(
            event.sender,
            self._to_public_verified_content(verified_content),
            event.room_id,
        )

    async def _handle_verify_accept(self, event: EventBase) -> None:
        content = dict(event.content)
        tx_hash = str(content.get("tx_hash", "")).strip()
        issuer_xrpl_address = str(content.get("issuer_xrpl_address", "")).strip()
        accepter_xrpl_address = str(content.get("accepter_xrpl_address", "")).strip()
        if not tx_hash or not issuer_xrpl_address or not accepter_xrpl_address:
            return

        tx_json, nft_token_id, uri = await self._validate_nft_modify_accept(
            tx_hash=tx_hash,
            expected_account=issuer_xrpl_address,
            expected_verifier=accepter_xrpl_address,
        )

        verified_content: JsonDict = {
            "status": "verified",
            "trust_model": "nft_metadata",
            "tx_hash": tx_hash,
            "user_id": event.sender,
            "issuer_xrpl_address": issuer_xrpl_address,
            "accepter_xrpl_address": accepter_xrpl_address,
            "nft_token_id": nft_token_id,
            "ipfs_uri": uri,
            "validated": True,
            "transaction_type": tx_json.get("TransactionType"),
        }

        await self._persist_verified_account_data(event.sender, verified_content)
        await self._notify_rooms(
            event.sender,
            self._to_public_verified_content(verified_content),
            event.room_id,
        )

    async def check_trust(self, payer_xrpl: str, payee_xrpl: str) -> bool:
        cache_key = self._trust_cache_key(payer_xrpl, payee_xrpl)
        cached = await self._external_cache.get(TRUST_CACHE_NAME, cache_key)
        if isinstance(cached, bool):
            return cached

        direct = await self._has_direct_trust(payer_xrpl, payee_xrpl)

        trusted = direct
        if not trusted:
            payer_to_payee, payee_to_payer = await self._check_mutual_directions(
                payer_xrpl,
                payee_xrpl,
            )
            trusted = payer_to_payee and payee_to_payer

        await self._external_cache.set(
            TRUST_CACHE_NAME,
            cache_key,
            trusted,
            expiry_ms=60_000,
        )
        return trusted

    async def _validate_nft_modify_accept(
        self,
        tx_hash: str,
        expected_account: str,
        expected_verifier: str,
    ) -> tuple[JsonDict, str, str]:
        tx_json = await self._fetch_validated_tx(tx_hash)
        tx = NFTokenModify.from_xrpl(tx_json)

        if tx.account != expected_account:
            raise ValueError("NFTokenModify account does not match issuer")

        nft_token_id = str(tx.nftoken_id or "").strip()
        if not nft_token_id:
            raise ValueError("Missing NFTokenID on NFTokenModify")

        identity_nft = await self._fetch_identity_nft(expected_account, nft_token_id)
        encoded_uri = str(tx.uri or identity_nft.get("URI") or "").strip()
        uri = decode_xrpl_uri(encoded_uri)
        verifiers = await self._load_verifiers_from_uri(uri)
        if expected_verifier.lower() not in verifiers:
            raise ValueError("Verifier not present in NFT metadata")

        return tx_json, nft_token_id, uri

    async def _fetch_validated_tx(self, tx_hash: str) -> JsonDict:
        xrpl_client = await self._xrpl_identity_handler.get_client()
        response = await xrpl_client.request(Tx(transaction=tx_hash))
        result = response.result
        if not result.get("validated"):
            raise ValueError("XRPL transaction is not validated yet")

        tx_json = result.get("tx_json") or result
        if not isinstance(tx_json, dict):
            raise ValueError("Unexpected XRPL tx response format")
        return tx_json

    async def _persist_verified_account_data(
        self,
        user_id: str,
        verified_content: JsonDict,
    ) -> None:
        existing = await self._store.get_global_account_data_by_type_for_user(
            user_id,
            VERIFIED_EVENT,
        )
        if isinstance(existing, dict) and existing.get("tx_hash") == verified_content.get(
            "tx_hash"
        ):
            return

        await self._account_data_handler.add_account_data_for_user(
            user_id,
            VERIFIED_EVENT,
            verified_content,
        )

    async def _check_mutual_directions(
        self,
        payer_xrpl: str,
        payee_xrpl: str,
    ) -> tuple[bool, bool]:
        payer_to_payee = await self._has_directional_trust(
            payer_xrpl,
            payee_xrpl,
        )
        payee_to_payer = await self._has_directional_trust(
            payee_xrpl,
            payer_xrpl,
        )
        return payer_to_payee, payee_to_payer

    async def _has_direct_trust(
        self,
        payer_xrpl: str,
        payee_xrpl: str,
    ) -> bool:
        return await self._has_directional_trust(payer_xrpl, payee_xrpl)

    async def _has_directional_trust(
        self,
        issuer_xrpl: str,
        subject_xrpl: str,
    ) -> bool:
        identity_nft = await self._fetch_identity_nft(issuer_xrpl)
        uri = decode_xrpl_uri(str(identity_nft.get("URI", "")).strip())
        verifiers = await self._load_verifiers_from_uri(uri)
        subject_lower = subject_xrpl.lower()
        return subject_lower in verifiers

    async def _fetch_identity_nft(
        self,
        xrpl_address: str,
        expected_nft_token_id: str | None = None,
    ) -> JsonDict:
        xrpl_client = await self._xrpl_identity_handler.get_client()
        marker: str | None = None
        expected = expected_nft_token_id.lower() if expected_nft_token_id else None
        for _ in range(2):
            response = await xrpl_client.request(
                AccountNFTs(
                    account=xrpl_address,
                    limit=200,
                    marker=marker,
                )
            )
            result = response.result
            account_nfts = result.get("account_nfts", [])
            if isinstance(account_nfts, list):
                for entry in account_nfts:
                    if not isinstance(entry, dict):
                        continue
                    token_id = str(entry.get("NFTokenID", "")).strip().lower()
                    uri = str(entry.get("URI", "")).strip()
                    if expected and token_id == expected:
                        return entry
                    if not expected and uri:
                        return entry
            marker = result.get("marker")
            if marker is None:
                break
        raise ValueError("Identity NFT not found for account")

    async def _load_verifiers_from_uri(self, uri: str) -> set[str]:
        if not uri:
            return set()

        cache_key = hashlib.sha256(uri.encode("utf-8")).hexdigest()
        cached = await self._external_cache.get(URI_METADATA_CACHE_NAME, cache_key)
        if isinstance(cached, str):
            try:
                metadata = json.loads(cached)
                return extract_verifiers_from_metadata(metadata)
            except Exception:
                pass

        metadata = await self._fetch_uri_metadata(uri)
        await self._external_cache.set(
            URI_METADATA_CACHE_NAME,
            cache_key,
            json.dumps(metadata),
            expiry_ms=60_000,
        )
        return extract_verifiers_from_metadata(metadata)

    async def _fetch_uri_metadata(self, uri: str) -> JsonDict:
        if uri.startswith("{"):
            parsed = json.loads(uri)
            if isinstance(parsed, dict):
                return parsed
            return {}

        if uri.startswith("data:application/json,"):
            payload = unquote(uri.split(",", 1)[1])
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
            return {}

        if uri.startswith("ipfs://"):
            cid_path = uri.removeprefix("ipfs://")
            gateway_url = f"https://ipfs.io/ipfs/{cid_path}"
            with urlopen(gateway_url, timeout=3.0) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {}

        return {}

    def _trust_cache_key(self, payer_xrpl: str, payee_xrpl: str) -> str:
        raw = f"{payer_xrpl.lower()}|{payee_xrpl.lower()}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    async def _resolve_xrpl_address_for_user(self, user_id: str) -> str | None:
        account_data = await self._store.get_global_account_data_by_type_for_user(
            user_id,
            XRPL_IDENTITY_ACCOUNT_DATA_EVENT,
        )
        if not isinstance(account_data, dict):
            return None

        xrpl_address = account_data.get("xrplAddress")
        if isinstance(xrpl_address, str) and xrpl_address:
            return xrpl_address
        return None

    def _extract_payee_user_id(
        self,
        content: JsonDict,
        state_events: StateMap[EventBase],
        payer_user_id: str,
    ) -> str | None:
        for key in ("payee_user_id", "recipient_user_id", "to_user_id", "payee"):
            value = content.get(key)
            if isinstance(value, str) and value.startswith("@"):
                return value

        # Fallback for direct chat rooms without explicit payee field.
        for (event_type, state_key), state_event in state_events.items():
            if event_type != EventTypes.Member:
                continue
            if state_key == payer_user_id:
                continue
            if state_event.membership == Membership.JOIN:
                return state_key
        return None

    def _to_public_verified_content(self, verified_content: JsonDict) -> JsonDict:
        public_content: JsonDict = {
            "status": verified_content.get("status"),
            "trust_model": verified_content.get("trust_model"),
            "tx_hash": verified_content.get("tx_hash"),
            "validated": verified_content.get("validated"),
            "transaction_type": verified_content.get("transaction_type"),
        }
        return public_content

    async def _notify_rooms(
        self,
        user_id: str,
        verified_content: JsonDict,
        origin_room_id: str | None,
    ) -> None:
        room_ids = set(await self._store.get_rooms_for_user(user_id))
        if origin_room_id:
            room_ids.add(origin_room_id)

        requester = create_requester(user_id, authenticated_entity=self._server_name)
        for room_id in room_ids:
            try:
                await self._event_creation_handler.create_and_send_nonmember_event(
                    requester,
                    {
                        "type": VERIFIED_EVENT,
                        "room_id": room_id,
                        "sender": user_id,
                        "state_key": user_id,
                        "content": verified_content,
                    },
                    ratelimit=False,
                )
            except Exception:
                logger.debug(
                    "Failed to send %s state update for user %s in room %s",
                    VERIFIED_EVENT,
                    user_id,
                    room_id,
                    exc_info=True,
                )


def decode_xrpl_uri(encoded: str) -> str:
    value = encoded.strip()
    if not value:
        return ""
    try:
        if len(value) % 2 == 0 and all(char in "0123456789abcdefABCDEF" for char in value):
            return bytes.fromhex(value).decode("utf-8")
    except Exception:
        pass
    return value


def extract_verifiers_from_metadata(metadata: Any) -> set[str]:
    if not isinstance(metadata, dict):
        return set()
    values = metadata.get("verifiers")
    if not isinstance(values, list):
        return set()
    return {
        str(value).strip().lower()
        for value in values
        if isinstance(value, str) and value.strip()
    }
