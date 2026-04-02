#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from http import HTTPStatus
import json
from typing import TYPE_CHECKING

from textrp_briij.api.errors import Codes, SynapseError
from textrp_briij.api.ratelimiting import Ratelimiter
from textrp_briij.http.server import HttpServer
from textrp_briij.http.servlet import RestServlet, parse_json_object_from_request
from textrp_briij.http.site import SynapseRequest
from textrp_briij.types import JsonDict

from ._base import client_patterns

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


class ZkpVerifyRestServlet(RestServlet):
    PATTERNS = client_patterns("/zkp/verify$")
    MAX_PROOF_BYTES = 64 * 1024
    MAX_SIGNALS_BYTES = 32 * 1024

    def __init__(self, hs: "HomeServer"):
        self.auth = hs.get_auth()
        self._store = hs.get_datastores().main
        self._ip_ratelimiter = Ratelimiter(
            store=self._store,
            clock=hs.get_clock(),
            cfg=hs.config.ratelimiting.rc_login_address,
        )
        self._wallet_ratelimiter = Ratelimiter(
            store=self._store,
            clock=hs.get_clock(),
            cfg=hs.config.ratelimiting.rc_login_account,
        )
        self.zkp_handler = hs.get_zkp_handler()

    async def on_POST(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        requester = await self.auth.get_user_by_req(request)
        body = parse_json_object_from_request(request)

        proof = body.get("proof")
        public_signals = body.get("public_signals")
        e2ee_pubkey_commitment = body.get("e2ee_pubkey_commitment")

        if not isinstance(proof, dict):
            raise SynapseError(400, "proof is required", errcode=Codes.MISSING_PARAM)
        if not isinstance(public_signals, dict):
            raise SynapseError(
                400, "public_signals is required", errcode=Codes.MISSING_PARAM
            )
        if len(json.dumps(proof, separators=(",", ":"))) > self.MAX_PROOF_BYTES:
            raise SynapseError(400, "proof is too large", errcode=Codes.INVALID_PARAM)
        if (
            len(json.dumps(public_signals, separators=(",", ":")))
            > self.MAX_SIGNALS_BYTES
        ):
            raise SynapseError(
                400,
                "public_signals is too large",
                errcode=Codes.INVALID_PARAM,
            )
        if not isinstance(e2ee_pubkey_commitment, str) or not e2ee_pubkey_commitment:
            e2ee_pubkey_commitment = public_signals.get("e2ee_pubkey_commitment")
        if not isinstance(e2ee_pubkey_commitment, str) or not e2ee_pubkey_commitment:
            raise SynapseError(
                400,
                "e2ee_pubkey_commitment is required",
                errcode=Codes.MISSING_PARAM,
            )

        xrpl_address = public_signals.get("xrpl_address")
        if not isinstance(xrpl_address, str) or not xrpl_address:
            raise SynapseError(
                400,
                "public_signals.xrpl_address is required",
                errcode=Codes.MISSING_PARAM,
            )
        if len(xrpl_address) > 64 or not xrpl_address.startswith("r"):
            raise SynapseError(
                400,
                "public_signals.xrpl_address is invalid",
                errcode=Codes.INVALID_PARAM,
            )
        await self._ip_ratelimiter.ratelimit(
            None,
            ("zkp_verify_ip", request.getClientAddress().host),
            rate_hz=5 / 60.0,
            burst_count=5,
        )
        await self._wallet_ratelimiter.ratelimit(
            None,
            ("zkp_verify_wallet", xrpl_address),
            rate_hz=20 / 3600.0,
            burst_count=20,
        )

        user_id = requester.user.to_string()
        result = await self.zkp_handler.verify_e2ee_binding(
            matrix_user_id=user_id,
            xrpl_address=xrpl_address,
            proof=proof,
            public_signals=public_signals,
            e2ee_pubkey_commitment=e2ee_pubkey_commitment,
        )
        return HTTPStatus.OK, result


def register_servlets(hs: "HomeServer", http_server: HttpServer) -> None:
    ZkpVerifyRestServlet(hs).register(http_server)
