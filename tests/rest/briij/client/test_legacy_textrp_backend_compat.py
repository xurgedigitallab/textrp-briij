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

from twisted.web.resource import Resource

from textrp_briij.rest import admin
from textrp_briij.rest.briij.client import build_briij_client_resource_tree
from textrp_briij.rest.client import login

from tests import unittest


class LegacyTextrpBackendCompatTests(unittest.HomeserverTestCase):
    servlets = [
        admin.register_servlets_for_client_rest_resource,
        login.register_servlets,
    ]

    def create_resource_dict(self) -> dict[str, Resource]:
        base = super().create_resource_dict()
        base.update(build_briij_client_resource_tree(self.hs))
        return base

    def prepare(self, reactor, clock, hs) -> None:
        self.store = hs.get_datastores().main

        self.user1_id = self.register_user("legacy_user_one", "pass")
        self.user2_id = self.register_user("legacy_user_two", "pass")
        self.user1_token = self.login("legacy_user_one", "pass")
        self.user2_token = self.login("legacy_user_two", "pass")

        self.wallet1 = "rWalletOne1111111111111111111111111"
        self.wallet2 = "rWalletTwo2222222222222222222222222"

        self.get_success(
            self.store.upsert_wallet_link(
                user_id=self.user1_id,
                wallet_address=self.wallet1,
                network="xrpl",
                public_key="pub1",
                linked_at=self.clock.time_msec(),
            )
        )
        self.get_success(
            self.store.upsert_wallet_link(
                user_id=self.user2_id,
                wallet_address=self.wallet2,
                network="xrpl",
                public_key="pub2",
                linked_at=self.clock.time_msec(),
            )
        )

        self.get_success(
            self.store.db_pool.simple_upsert(
                table="mcredit_balances",
                keyvalues={"user_id": self.user1_id},
                values={"balance": 350, "updated_ts": self.clock.time_msec()},
                desc="set_user1_balance",
            )
        )

        self.get_success(
            self.store.db_pool.simple_insert(
                table="premium_features",
                values={
                    "feature_id": 4001,
                    "feature_key": "voip_premium",
                    "name": "VoIP Premium",
                    "description": "Paid VoIP access",
                    "mcredits_cost": 200,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="insert_voip_premium",
            )
        )
        self.get_success(
            self.store.db_pool.simple_insert(
                table="premium_features",
                values={
                    "feature_id": 4002,
                    "feature_key": "teleconference_hd",
                    "name": "Teleconference HD",
                    "description": "Higher tier calling",
                    "mcredits_cost": 500,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="insert_teleconference_hd",
            )
        )

    def test_my_address_requires_auth(self) -> None:
        channel = self.make_request(
            "POST",
            "/my-address",
            content={"address": self.user1_id},
            shorthand=False,
        )
        self.assertEqual(channel.code, 401)

    def test_my_address_success(self) -> None:
        channel = self.make_request(
            "POST",
            "/my-address",
            content={"address": self.user1_id},
            access_token=self.user1_token,
            shorthand=False,
        )
        self.assertEqual(channel.code, 200)
        self.assertEqual(channel.json_body["address"], self.wallet1)
        self.assertEqual(channel.json_body["user"]["address"], self.wallet1)
        self.assertEqual(channel.json_body["user"]["credit"]["balance"], "350")

    def test_my_address_forbids_other_user_lookup(self) -> None:
        channel = self.make_request(
            "POST",
            "/my-address",
            content={"address": self.user2_id},
            access_token=self.user1_token,
            shorthand=False,
        )
        self.assertEqual(channel.code, 403)

    def test_my_features_enabled_filters_by_balance(self) -> None:
        channel = self.make_request(
            "GET",
            f"/my-features/{self.wallet1}/main/enabled",
            access_token=self.user1_token,
            shorthand=False,
        )
        self.assertEqual(channel.code, 200)
        features = [entry["feature"] for entry in channel.json_body["nfts"]]
        self.assertEqual(features, ["voip_premium"])

    def test_my_features_forbids_other_user_lookup(self) -> None:
        channel = self.make_request(
            "GET",
            f"/my-features/{self.wallet1}/main/enabled",
            access_token=self.user2_token,
            shorthand=False,
        )
        self.assertEqual(channel.code, 403)

    def test_my_features_rejects_unknown_network(self) -> None:
        channel = self.make_request(
            "GET",
            f"/my-features/{self.wallet1}/test/enabled",
            access_token=self.user1_token,
            shorthand=False,
        )
        self.assertEqual(channel.code, 400)
