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

from twisted.internet.testing import MemoryReactor

import textrp_briij.rest.admin
from textrp_briij.rest.client import login, mcredits, register
from textrp_briij.server import HomeServer
from textrp_briij.util.clock import Clock

from tests import unittest


class MCreditRestTestCase(unittest.HomeserverTestCase):
    servlets = [
        textrp_briij.rest.admin.register_servlets_for_client_rest_resource,
        login.register_servlets,
        register.register_servlets,
        mcredits.register_servlets,
    ]

    def make_homeserver(self, reactor: MemoryReactor, clock: Clock) -> HomeServer:
        return self.setup_test_homeserver()

    def prepare(self, reactor: MemoryReactor, clock: Clock, hs: HomeServer) -> None:
        self.store = hs.get_datastores().main
        self.localpart = "mcredit_rest_user"
        self.password = "pass"
        self.user_id = self.register_user(self.localpart, self.password)
        self.token = self.login(self.localpart, self.password)

    def _insert_feature(self, feature_id: int, key: str, cost: int) -> None:
        self.get_success(
            self.store.db_pool.simple_insert(
                "premium_features",
                {
                    "feature_id": feature_id,
                    "feature_key": key,
                    "name": key,
                    "description": key,
                    "mcredits_cost": cost,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc=f"insert_feature_{key}",
            )
        )

    def _set_balance(self, balance: int) -> None:
        self.get_success(
            self.store.db_pool.simple_upsert(
                table="mcredit_balances",
                keyvalues={"user_id": self.user_id},
                values={"balance": balance, "updated_ts": self.clock.time_msec()},
                insertion_values={
                    "balance": balance,
                    "updated_ts": self.clock.time_msec(),
                },
                desc="set_test_user_balance",
            )
        )

    def test_auth_required(self) -> None:
        channel = self.make_request("GET", "/_matrix/client/v3/mcredits/balance")
        self.assertEqual(channel.code, 401)

    def test_get_features(self) -> None:
        self._insert_feature(1, "voip_premium", 200)
        channel = self.make_request(
            "GET",
            "/_matrix/client/v3/mcredits/features",
            access_token=self.token,
        )
        self.assertEqual(channel.code, 200)
        self.assertEqual(len(channel.json_body["features"]), 1)
        self.assertEqual(channel.json_body["features"][0]["feature_key"], "voip_premium")

    def test_spend_success(self) -> None:
        self._set_balance(1000)
        self._insert_feature(2, "teleconference_hd", 250)
        channel = self.make_request(
            "POST",
            "/_matrix/client/v3/mcredits/spend",
            {"feature_key": "teleconference_hd"},
            access_token=self.token,
        )
        self.assertEqual(channel.code, 200)
        self.assertEqual(channel.json_body["balance"], 750)

    def test_spend_insufficient_credits(self) -> None:
        self._set_balance(1000)
        # Drain most of the balance first.
        self._insert_feature(3, "big_spend", 950)
        self._insert_feature(4, "ai_summary", 100)
        first = self.make_request(
            "POST",
            "/_matrix/client/v3/mcredits/spend",
            {"feature_key": "big_spend"},
            access_token=self.token,
        )
        self.assertEqual(first.code, 200)

        second = self.make_request(
            "POST",
            "/_matrix/client/v3/mcredits/spend",
            {"feature_key": "ai_summary"},
            access_token=self.token,
        )
        self.assertEqual(second.code, 402)

    def test_spend_unknown_feature(self) -> None:
        channel = self.make_request(
            "POST",
            "/_matrix/client/v3/mcredits/spend",
            {"feature_key": "does_not_exist"},
            access_token=self.token,
        )
        self.assertEqual(channel.code, 404)
