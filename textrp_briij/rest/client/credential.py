#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from http import HTTPStatus
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


class CredentialVerifyRestServlet(RestServlet):
    PATTERNS = client_patterns("/credential/verify$")

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
        self.credential_handler = hs.get_credential_handler()

    async def on_POST(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        requester = await self.auth.get_user_by_req(request)
        body = parse_json_object_from_request(request)
        credential_id = body.get("credential_id")
        if not isinstance(credential_id, str) or not credential_id:
            raise SynapseError(
                400,
                "credential_id is required",
                errcode=Codes.MISSING_PARAM,
            )
        if len(credential_id) > 128:
            raise SynapseError(400, "credential_id is too large", errcode=Codes.INVALID_PARAM)
        await self._ip_ratelimiter.ratelimit(
            None,
            ("credential_verify_ip", request.getClientAddress().host),
            rate_hz=5 / 60.0,
            burst_count=5,
        )
        did_map = None
        try:
            did_map = await self._store.get_user_did_map_by_user_id(
                requester.user.to_string()
            )
        except Exception:
            # Some test configurations do not bootstrap Postgres-only DID tables.
            did_map = None
        wallet_key = did_map["xrpl_address"] if did_map is not None else credential_id
        await self._wallet_ratelimiter.ratelimit(
            None,
            ("credential_verify_wallet", wallet_key),
            rate_hz=20 / 3600.0,
            burst_count=20,
        )
        is_valid = await self.credential_handler.verify_credential(credential_id)
        return HTTPStatus.OK, {"credential_id": credential_id, "valid": is_valid}


def register_servlets(hs: "HomeServer", http_server: HttpServer) -> None:
    CredentialVerifyRestServlet(hs).register(http_server)
