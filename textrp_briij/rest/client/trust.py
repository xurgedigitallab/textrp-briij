#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 TextRP https://textrp.io
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
from __future__ import annotations

from typing import TYPE_CHECKING

from textrp_briij.http.server import HttpServer
from textrp_briij.http.servlet import RestServlet, parse_string
from textrp_briij.http.site import SynapseRequest
from textrp_briij.types import JsonDict

from ._base import client_patterns

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


class XrplTrustServlet(RestServlet):
    """
    GET /org.textrp.xrpl/trust?payer={rAddress}&payee={rAddress} HTTP/1.1
    """

    PATTERNS = client_patterns("/org.textrp.xrpl/trust$")

    def __init__(self, hs: "HomeServer"):
        super().__init__()
        self._auth = hs.get_auth()
        self._verification_handler = hs.get_verification_handler()

    async def on_GET(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        await self._auth.get_user_by_req(request)

        payer = parse_string(request, "payer", required=True)
        payee = parse_string(request, "payee", required=True)

        trusted = await self._verification_handler.check_trust(
            payer_xrpl=payer,
            payee_xrpl=payee,
        )
        return 200, {
            "score": 1 if trusted else 0,
            "trusted": trusted,
        }


def register_servlets(hs: "HomeServer", http_server: HttpServer) -> None:
    XrplTrustServlet(hs).register(http_server)
