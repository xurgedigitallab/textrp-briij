#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 Xurge Digital Lab
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from http import HTTPStatus
from typing import TYPE_CHECKING

from textrp_briij.api.errors import Codes, SynapseError
from textrp_briij.http.server import HttpServer
from textrp_briij.http.servlet import RestServlet, parse_json_object_from_request
from textrp_briij.http.site import SynapseRequest
from textrp_briij.types import JsonDict

from ._base import client_patterns

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


class MCreditFeaturesRestServlet(RestServlet):
    PATTERNS = client_patterns("/mcredits/features$")

    def __init__(self, hs: "HomeServer"):
        self.auth = hs.get_auth()
        self.store = hs.get_datastores().main

    async def on_GET(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        await self.auth.get_user_by_req(request)
        features = await self.store.get_active_premium_features()
        return HTTPStatus.OK, {"features": features}


class MCreditBalanceRestServlet(RestServlet):
    PATTERNS = client_patterns("/mcredits/balance$")

    def __init__(self, hs: "HomeServer"):
        self.auth = hs.get_auth()
        self.store = hs.get_datastores().main

    async def on_GET(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        requester = await self.auth.get_user_by_req(request)
        balance = await self.store.get_mcredit_balance(requester.user.to_string())
        return HTTPStatus.OK, {"balance": balance}


class MCreditSpendRestServlet(RestServlet):
    PATTERNS = client_patterns("/mcredits/spend$")

    def __init__(self, hs: "HomeServer"):
        self.auth = hs.get_auth()
        self.mcredit_handler = hs.get_mcredit_handler()

    async def on_POST(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        requester = await self.auth.get_user_by_req(request)
        body = parse_json_object_from_request(request)
        feature_key = body.get("feature_key")
        if not isinstance(feature_key, str) or not feature_key:
            raise SynapseError(
                400,
                "feature_key is required",
                errcode=Codes.MISSING_PARAM,
            )

        new_balance = await self.mcredit_handler.spend_mcredits(requester, feature_key)
        return HTTPStatus.OK, {"feature_key": feature_key, "balance": new_balance}


def register_servlets(hs: "HomeServer", http_server: HttpServer) -> None:
    MCreditFeaturesRestServlet(hs).register(http_server)
    MCreditBalanceRestServlet(hs).register(http_server)
    MCreditSpendRestServlet(hs).register(http_server)
