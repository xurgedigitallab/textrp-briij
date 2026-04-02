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
    from textrp_briij.synapse_rust import zkp as rust_zkp
except ImportError:  # pragma: no cover
    rust_zkp = None


class ZkpHandler:
    def __init__(self, hs: "HomeServer"):
        self._store = hs.get_datastores().main
        self._clock = hs.get_clock()

    async def verify_e2ee_binding(
        self,
        matrix_user_id: str,
        xrpl_address: str,
        proof: dict[str, Any],
        public_signals: dict[str, Any],
        e2ee_pubkey_commitment: str,
    ) -> dict[str, Any]:
        self._ensure_rust_zkp()
        did_map = await self._store.get_user_did_map_by_user_id(matrix_user_id)
        if did_map is None:
            raise ValueError("No DID mapping for user")
        credential_id = did_map.get("credential_id")
        did_uri = did_map.get("did_uri")
        if not credential_id or not did_uri:
            raise ValueError("Missing DID or credential binding for ZKP verification")

        result = dict(
            rust_zkp.verify_zkp_binding(
                {
                    "proof": proof,
                    "public_signals": public_signals,
                    "expected_did_uri": did_uri,
                    "expected_xrpl_address": xrpl_address,
                    "expected_credential_id": credential_id,
                    "expected_e2ee_pubkey_commitment": e2ee_pubkey_commitment,
                }
            )
        )

        await self._store.upsert_user_did_map(
            matrix_user_id=matrix_user_id,
            xrpl_address=xrpl_address,
            did_uri=did_uri,
            did_document_hash=did_map.get("did_document_hash"),
            credential_id=credential_id,
            credential_issued_at=did_map.get("credential_issued_at"),
            e2ee_pubkey_commitment=e2ee_pubkey_commitment,
            e2ee_zkp_verified_at=self._clock.time_msec() if result.get("valid") else None,
        )
        return result

    def _ensure_rust_zkp(self) -> None:
        if rust_zkp is None:
            logger.error("Rust zkp module is unavailable; rebuild synapse_rust extension")
            raise ValueError("Rust zkp module is unavailable")
