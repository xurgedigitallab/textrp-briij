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
from textrp_briij.http.servlet import RestServlet, parse_string
from textrp_briij.http.site import SynapseRequest
from textrp_briij.types import JsonDict

from ._base import client_patterns

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


class DidResolveRestServlet(RestServlet):
    PATTERNS = client_patterns("/did/resolve$")

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
        self.did_handler = hs.get_did_handler()

    async def on_GET(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        await self.auth.get_user_by_req(request)
        account = parse_string(request, "account", required=True)
        assert account is not None
        if len(account) > 64 or not account.startswith("r"):
            raise SynapseError(400, "Invalid XRPL account", errcode=Codes.INVALID_PARAM)
        await self._ip_ratelimiter.ratelimit(
            None,
            ("did_resolve_ip", request.getClientAddress().host),
            rate_hz=5 / 60.0,
            burst_count=5,
        )
        await self._wallet_ratelimiter.ratelimit(
            None,
            ("did_resolve_wallet", account),
            rate_hz=20 / 3600.0,
            burst_count=20,
        )
        result = await self.did_handler.resolve_did_document(account)
        return HTTPStatus.OK, result


def register_servlets(hs: "HomeServer", http_server: HttpServer) -> None:
    DidResolveRestServlet(hs).register(http_server)
