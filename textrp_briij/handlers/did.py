#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer

logger = logging.getLogger(__name__)

try:
    from textrp_briij.synapse_rust import did as rust_did
except ImportError:  # pragma: no cover - only for environments without rebuilt rust module.
    rust_did = None


class DidHandler:
    def __init__(self, hs: "HomeServer"):
        self._store = hs.get_datastores().main

    async def resolve_did_document(self, account: str) -> dict[str, Any]:
        self._ensure_rust_did()
        result = rust_did.resolve_did_document(account)
        return dict(result)

    async def verify_did_control(self, account: str, proof: str) -> bool:
        self._ensure_rust_did()
        return bool(rust_did.verify_did_control(account, proof))

    async def commit_wallet_did_binding(
        self,
        matrix_user_id: str,
        xrpl_address: str,
        *,
        e2ee_commitment: str,
    ) -> dict[str, Any]:
        self._ensure_rust_did()

        did_uri = f"did:xrpl:testnet:{xrpl_address}"
        did_document_json = (
            f'{{"id":"{did_uri}","service":[{{"id":"{did_uri}#e2ee","type":"E2EECommitment","serviceEndpoint":"{e2ee_commitment}"}}]}}'
        )
        ledger_entry = rust_did.submit_did_set(
            {
                "account": xrpl_address,
                "did_uri": did_uri,
                "did_document_json": did_document_json,
                "e2ee_commitment": e2ee_commitment,
            }
        )
        existing = await self._store.get_user_did_map_by_user_id(matrix_user_id)

        await self._store.upsert_user_did_map(
            matrix_user_id=matrix_user_id,
            xrpl_address=xrpl_address,
            did_uri=did_uri,
            did_document_hash=ledger_entry.get("did_document_hash"),
            credential_id=existing.get("credential_id") if existing is not None else None,
            credential_issued_at=(
                existing.get("credential_issued_at") if existing is not None else None
            ),
            e2ee_pubkey_commitment=(
                existing.get("e2ee_pubkey_commitment") if existing is not None else None
            ),
            e2ee_zkp_verified_at=(
                existing.get("e2ee_zkp_verified_at") if existing is not None else None
            ),
        )

        return dict(ledger_entry)

    def _ensure_rust_did(self) -> None:
        if rust_did is None:
            logger.error("Rust DID module is unavailable; rebuild synapse_rust extension")
            raise ValueError("Rust DID module is unavailable")
