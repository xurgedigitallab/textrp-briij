#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

import re
from typing import TYPE_CHECKING, Any

from textrp_briij.api.errors import Codes, SynapseError
from textrp_briij.http.server import DirectServeJsonResource, JsonResource
from textrp_briij.http.servlet import parse_json_object_from_request
from textrp_briij.http.site import SynapseRequest
from textrp_briij.types import JsonDict

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


def _pick_wallet_address(links: list[dict[str, Any]]) -> str | None:
    if not links:
        return None

    # Prefer XRPL links first, then most recently linked wallets.
    ordered_links = sorted(
        links,
        key=lambda link: (link.get("network") != "xrpl", -(int(link.get("linked_at") or 0))),
    )

    wallet_address = ordered_links[0].get("wallet_address")
    return wallet_address if isinstance(wallet_address, str) else None


class LegacyMyAddressResource(DirectServeJsonResource):
    """Legacy compatibility endpoint for `POST /my-address`."""

    def __init__(self, hs: "HomeServer"):
        super().__init__(clock=hs.get_clock())
        self._auth = hs.get_auth()
        self._store = hs.get_datastores().main

    async def _async_render_POST(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        requester = await self._auth.get_user_by_req(request)
        body = parse_json_object_from_request(request)
        address = body.get("address")

        if not isinstance(address, str) or not address:
            raise SynapseError(400, "address is required", errcode=Codes.MISSING_PARAM)

        requester_user_id = requester.user.to_string()
        if address != requester_user_id:
            raise SynapseError(
                403,
                "You can only query your own address",
                errcode=Codes.FORBIDDEN,
            )

        links = await self._store.get_wallet_links_by_user(address)
        wallet_address = _pick_wallet_address(links)
        if wallet_address is None:
            raise SynapseError(404, "Wallet link not found", errcode=Codes.NOT_FOUND)

        balance = await self._store.get_mcredit_balance(address)
        return (
            200,
            {
                "user": {
                    "address": wallet_address,
                    "credit": {"balance": str(balance)},
                },
                "address": wallet_address,
            },
        )


class LegacyMyFeaturesResource(JsonResource):
    """Legacy compatibility endpoint for `GET /my-features/.../enabled`."""

    def __init__(self, hs: "HomeServer"):
        super().__init__(hs, canonical_json=False)
        self._auth = hs.get_auth()
        self._store = hs.get_datastores().main
        self.register_paths(
            "GET",
            (
                re.compile(
                    r"^/my-features/(?P<wallet_address>[^/]+)/(?P<network>[^/]+)/enabled$"
                ),
            ),
            self._on_get_enabled,
            self.__class__.__name__,
        )

    async def _on_get_enabled(
        self, request: SynapseRequest, wallet_address: str, network: str
    ) -> tuple[int, JsonDict]:
        requester = await self._auth.get_user_by_req(request)

        if network != "main":
            raise SynapseError(
                400,
                "network must be 'main' for this compatibility endpoint",
                errcode=Codes.INVALID_PARAM,
            )

        wallet_link = await self._store.get_wallet_link_by_address(wallet_address, "xrpl")
        if wallet_link is None:
            wallet_link = await self._store.get_wallet_link_by_address(
                wallet_address, "xahau"
            )
        if wallet_link is None:
            raise SynapseError(404, "Wallet link not found", errcode=Codes.NOT_FOUND)

        requester_user_id = requester.user.to_string()
        owner_user_id = wallet_link["user_id"]
        if owner_user_id != requester_user_id:
            raise SynapseError(
                403,
                "You can only query your own enabled features",
                errcode=Codes.FORBIDDEN,
            )

        balance = await self._store.get_mcredit_balance(owner_user_id)
        rows = await self._store.db_pool.simple_select_list(
            table="premium_features",
            keyvalues={"is_active": True},
            retcols=(
                "feature_key",
                "name",
                "description",
                "mcredits_cost",
                "category",
            ),
            desc="legacy_enabled_features",
        )

        nfts = []
        for row in rows:
            feature_key = row[0]
            name = row[1]
            description = row[2]
            mcredits_cost = int(row[3])
            category = row[4]
            if balance >= mcredits_cost:
                nfts.append(
                    {
                        "feature": feature_key,
                        "name": name,
                        "description": description,
                        "mcredits_cost": mcredits_cost,
                        "category": category,
                    }
                )

        return 200, {"nfts": nfts}
