# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 TextRP https://textrp.io
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from xrpl.models.requests import Tx
from xrpl.models.transactions import CredentialAccept, CredentialCreate

from textrp_briij.events import EventBase
from textrp_briij.types import JsonDict, create_requester

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer

logger = logging.getLogger(__name__)

VERIFY_REQUEST_EVENT = "m.user.verify.request"
VERIFY_ACCEPT_EVENT = "m.user.verify.accept"
VERIFIED_EVENT = "m.user.verified"

# XLS-70 credential type must be exactly b'textrp_verify'.
CREDENTIAL_TYPE_BYTES = b"textrp_verify"
CREDENTIAL_TYPE_HEX = CREDENTIAL_TYPE_BYTES.hex().upper()


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

        self._event_handlers = {
            VERIFY_REQUEST_EVENT: self._handle_verify_request,
            VERIFY_ACCEPT_EVENT: self._handle_verify_accept,
        }

        hs.get_module_api_callbacks().third_party_event_rules.register_third_party_rules_callbacks(
            on_new_event=self._on_new_event,
        )

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
        tx_hash = str(content.get("tx_hash", "")).strip()
        issuer_xrpl_address = str(content.get("issuer_xrpl_address", "")).strip()
        target_xrpl_address = str(content.get("target_xrpl_address", "")).strip()
        if not tx_hash or not issuer_xrpl_address or not target_xrpl_address:
            return

        tx_json = await self._validate_credential_create(
            tx_hash=tx_hash,
            expected_account=issuer_xrpl_address,
            expected_subject=target_xrpl_address,
        )

        verified_content: JsonDict = {
            "status": "requested",
            "credential_type": "textrp_verify",
            "credential_type_bytes": CREDENTIAL_TYPE_BYTES.decode("ascii"),
            "tx_hash": tx_hash,
            "requester_user_id": event.sender,
            "issuer_xrpl_address": issuer_xrpl_address,
            "target_xrpl_address": target_xrpl_address,
            "validated": True,
            "transaction_type": tx_json.get("TransactionType"),
        }

        await self._persist_verified_account_data(event.sender, verified_content)
        await self._notify_rooms(event.sender, verified_content, event.room_id)

    async def _handle_verify_accept(self, event: EventBase) -> None:
        content = dict(event.content)
        tx_hash = str(content.get("tx_hash", "")).strip()
        issuer_xrpl_address = str(content.get("issuer_xrpl_address", "")).strip()
        accepter_xrpl_address = str(content.get("accepter_xrpl_address", "")).strip()
        if not tx_hash or not issuer_xrpl_address or not accepter_xrpl_address:
            return

        tx_json = await self._validate_credential_accept(
            tx_hash=tx_hash,
            expected_account=accepter_xrpl_address,
            expected_issuer=issuer_xrpl_address,
        )

        verified_content: JsonDict = {
            "status": "verified",
            "credential_type": "textrp_verify",
            "credential_type_bytes": CREDENTIAL_TYPE_BYTES.decode("ascii"),
            "tx_hash": tx_hash,
            "user_id": event.sender,
            "issuer_xrpl_address": issuer_xrpl_address,
            "accepter_xrpl_address": accepter_xrpl_address,
            "validated": True,
            "transaction_type": tx_json.get("TransactionType"),
        }

        await self._persist_verified_account_data(event.sender, verified_content)
        await self._notify_rooms(event.sender, verified_content, event.room_id)

    async def _validate_credential_create(
        self,
        tx_hash: str,
        expected_account: str,
        expected_subject: str,
    ) -> JsonDict:
        tx_json = await self._fetch_validated_tx(tx_hash)
        tx = CredentialCreate.from_xrpl(tx_json)
        if str(tx.credential_type).upper() != CREDENTIAL_TYPE_HEX:
            raise ValueError("Invalid CredentialType for verification request")

        if tx.account != expected_account:
            raise ValueError("CredentialCreate account does not match issuer")

        if tx.subject != expected_subject:
            raise ValueError("CredentialCreate subject does not match target")

        return tx_json

    async def _validate_credential_accept(
        self,
        tx_hash: str,
        expected_account: str,
        expected_issuer: str,
    ) -> JsonDict:
        tx_json = await self._fetch_validated_tx(tx_hash)
        tx = CredentialAccept.from_xrpl(tx_json)
        if str(tx.credential_type).upper() != CREDENTIAL_TYPE_HEX:
            raise ValueError("Invalid CredentialType for verification acceptance")

        if tx.account != expected_account:
            raise ValueError("CredentialAccept account does not match accepter")

        if tx.issuer != expected_issuer:
            raise ValueError("CredentialAccept issuer does not match expected issuer")

        return tx_json

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
