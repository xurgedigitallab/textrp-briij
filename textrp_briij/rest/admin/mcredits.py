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

from textrp_briij.api.errors import Codes, NotFoundError, SynapseError
from textrp_briij.http.servlet import RestServlet, parse_json_object_from_request
from textrp_briij.http.site import SynapseRequest
from textrp_briij.rest.admin._base import admin_patterns, assert_requester_is_admin
from textrp_briij.types import JsonDict

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


def _validate_positive_cost(cost: object) -> int:
    if not isinstance(cost, int) or cost <= 0:
        raise SynapseError(
            HTTPStatus.BAD_REQUEST,
            "mcredits_cost must be a positive integer",
            errcode=Codes.INVALID_PARAM,
        )
    return cost


def _feature_row_to_json(row: tuple) -> JsonDict:
    """Convert a raw runInteraction tuple from premium_features into JSON.

    Expects tuple order:
    (feature_id, feature_key, name, description, mcredits_cost, category, is_active, created_ts).
    Only use for raw tuple result paths. Dict-returning paths like
    get_premium_feature_by_key and handlers in on_POST/on_PUT/on_DELETE should not use it.
    """
    return {
        "feature_id": row[0],
        "feature_key": row[1],
        "name": row[2],
        "description": row[3],
        "mcredits_cost": row[4],
        "category": row[5],
        "is_active": bool(row[6]),
        "created_ts": row[7],
    }


class PremiumFeaturesRestServlet(RestServlet):
    PATTERNS = admin_patterns("/briij/premium_features$", "v2")

    def __init__(self, hs: "HomeServer"):
        self.auth = hs.get_auth()
        self.store = hs.get_datastores().main
        self.clock = hs.get_clock()

    async def on_GET(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        await assert_requester_is_admin(self.auth, request)

        def _get_features_txn(txn) -> list[tuple]:
            txn.execute(
                """
                SELECT feature_id, feature_key, name, description, mcredits_cost, category, is_active, created_ts
                FROM premium_features
                ORDER BY feature_id ASC
                """
            )
            return txn.fetchall()

        rows = await self.store.db_pool.runInteraction(
            "admin_get_premium_features", _get_features_txn
        )
        return HTTPStatus.OK, {"premium_features": [_feature_row_to_json(r) for r in rows]}

    async def on_POST(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        await assert_requester_is_admin(self.auth, request)
        body = parse_json_object_from_request(request)

        feature_key = body.get("feature_key")
        name = body.get("name")
        description = body.get("description")
        category = body.get("category")
        mcredits_cost = _validate_positive_cost(body.get("mcredits_cost"))

        if not isinstance(feature_key, str) or not feature_key:
            raise SynapseError(
                HTTPStatus.BAD_REQUEST,
                "feature_key is required",
                errcode=Codes.INVALID_PARAM,
            )
        if not isinstance(name, str) or not name:
            raise SynapseError(
                HTTPStatus.BAD_REQUEST,
                "name is required",
                errcode=Codes.INVALID_PARAM,
            )
        if description is not None and not isinstance(description, str):
            raise SynapseError(
                HTTPStatus.BAD_REQUEST,
                "description must be a string",
                errcode=Codes.INVALID_PARAM,
            )
        if category is not None and not isinstance(category, str):
            raise SynapseError(
                HTTPStatus.BAD_REQUEST,
                "category must be a string",
                errcode=Codes.INVALID_PARAM,
            )

        await self.store.db_pool.simple_insert(
            "premium_features",
            {
                "feature_key": feature_key,
                "name": name,
                "description": description,
                "mcredits_cost": mcredits_cost,
                "category": category,
                "is_active": True,
                "created_ts": self.clock.time_msec(),
            },
            desc="admin_create_premium_feature",
        )

        row = await self.store.get_premium_feature_by_key(feature_key)
        assert row is not None
        return HTTPStatus.OK, row


class PremiumFeatureByKeyRestServlet(RestServlet):
    PATTERNS = admin_patterns("/briij/premium_features/(?P<feature_key>[^/]*)$", "v2")

    def __init__(self, hs: "HomeServer"):
        self.auth = hs.get_auth()
        self.store = hs.get_datastores().main

    async def on_PUT(
        self, request: SynapseRequest, feature_key: str
    ) -> tuple[int, JsonDict]:
        await assert_requester_is_admin(self.auth, request)
        body = parse_json_object_from_request(request)

        current = await self.store.get_premium_feature_by_key(feature_key)
        if current is None:
            raise NotFoundError("Premium feature not found")

        update_values: dict[str, object] = {}

        if "mcredits_cost" in body:
            update_values["mcredits_cost"] = _validate_positive_cost(body["mcredits_cost"])
        if "description" in body:
            description = body["description"]
            if description is not None and not isinstance(description, str):
                raise SynapseError(
                    HTTPStatus.BAD_REQUEST,
                    "description must be a string",
                    errcode=Codes.INVALID_PARAM,
                )
            update_values["description"] = description
        if "is_active" in body:
            is_active = body["is_active"]
            if not isinstance(is_active, bool):
                raise SynapseError(
                    HTTPStatus.BAD_REQUEST,
                    "is_active must be a boolean",
                    errcode=Codes.INVALID_PARAM,
                )
            update_values["is_active"] = is_active

        if not update_values:
            raise SynapseError(
                HTTPStatus.BAD_REQUEST,
                "At least one updatable field is required",
                errcode=Codes.INVALID_PARAM,
            )

        await self.store.db_pool.simple_update_one(
            table="premium_features",
            keyvalues={"feature_key": feature_key},
            updatevalues=update_values,
            desc="admin_update_premium_feature",
        )
        row = await self.store.get_premium_feature_by_key(feature_key)
        assert row is not None
        return HTTPStatus.OK, row

    async def on_DELETE(
        self, request: SynapseRequest, feature_key: str
    ) -> tuple[int, JsonDict]:
        await assert_requester_is_admin(self.auth, request)

        current = await self.store.get_premium_feature_by_key(feature_key)
        if current is None:
            raise NotFoundError("Premium feature not found")

        await self.store.db_pool.simple_update_one(
            table="premium_features",
            keyvalues={"feature_key": feature_key},
            updatevalues={"is_active": False},
            desc="admin_soft_delete_premium_feature",
        )
        row = await self.store.get_premium_feature_by_key(feature_key)
        assert row is not None
        return HTTPStatus.OK, row
