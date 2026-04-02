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

from textrp_briij.api.ratelimiting import Ratelimiter

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer

logger = logging.getLogger(__name__)

try:
    from textrp_briij.synapse_rust import credential as rust_credential
except ImportError:  # pragma: no cover - only for environments without rebuilt rust module.
    rust_credential = None


class CredentialHandler:
    def __init__(self, hs: "HomeServer"):
        self._hs = hs
        self._store = hs.get_datastores().main
        self._clock = hs.get_clock()
        self._did_handler = hs.get_did_handler()
        self._credential_ratelimiter = Ratelimiter(
            store=self._store,
            clock=self._clock,
            cfg=hs.config.ratelimiting.rc_login_account,
        )

    async def issue_login_credential(
        self,
        matrix_user_id: str,
        xrpl_address: str,
        e2ee_pubkey_commitment: str,
    ) -> dict[str, Any]:
        self._ensure_rust_credential()
        await self._credential_ratelimiter.ratelimit(
            None,
            ("credential_issue", xrpl_address, matrix_user_id),
        )

        existing = await self._store.get_user_did_map_by_user_id(matrix_user_id)
        if existing is not None and existing.get("credential_id"):
            return {
                "credential_id": existing["credential_id"],
                "status": "issued",
                "duplicate": True,
            }

        did_uri: str | None = existing.get("did_uri") if existing is not None else None
        if not did_uri:
            did_doc = await self._did_handler.resolve_did_document(xrpl_address)
            did_uri = did_doc.get("did_uri")

        result = dict(
            rust_credential.submit_credential_create(
                {
                    "subject": xrpl_address,
                    "did_uri": did_uri,
                    "matrix_user_id": matrix_user_id,
                    "e2ee_pubkey_commitment": e2ee_pubkey_commitment,
                }
            )
        )

        await self._store.upsert_user_did_map(
            matrix_user_id=matrix_user_id,
            xrpl_address=xrpl_address,
            did_uri=did_uri,
            did_document_hash=(
                existing.get("did_document_hash") if existing is not None else None
            ),
            credential_id=result.get("credential_id"),
            credential_issued_at=self._clock.time_msec(),
            e2ee_pubkey_commitment=e2ee_pubkey_commitment,
            e2ee_zkp_verified_at=(
                existing.get("e2ee_zkp_verified_at") if existing is not None else None
            ),
        )
        return result

    async def verify_credential(self, credential_id: str) -> bool:
        self._ensure_rust_credential()
        return bool(rust_credential.verify_credential(credential_id))

    async def revoke_credential(self, credential_id: str) -> dict[str, Any]:
        self._ensure_rust_credential()
        return dict(
            rust_credential.submit_credential_delete({"credential_id": credential_id})
        )

    def _ensure_rust_credential(self) -> None:
        if rust_credential is None:
            logger.error(
                "Rust credential module is unavailable; rebuild synapse_rust extension"
            )
            raise ValueError("Rust credential module is unavailable")
