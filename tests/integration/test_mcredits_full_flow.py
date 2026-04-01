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


class MCreditsFullFlowTestCase(unittest.HomeserverTestCase):
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

    def test_mcredits_full_flow(self) -> None:
        localpart = "mcredit_full_flow"
        password = "pass"
        user_id = self.register_user(localpart, password)
        token = self.login(localpart, password)

        self.get_success(
            self.store.db_pool.simple_insert(
                "premium_features",
                {
                    "feature_id": 800,
                    "feature_key": "voip_premium",
                    "name": "VoIP Premium",
                    "description": "Premium voice calls",
                    "mcredits_cost": 700,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="test_mcredits_full_flow_insert_feature",
            )
        )

        # List features.
        features_res = self.make_request(
            "GET",
            "/_matrix/client/v3/mcredits/features",
            access_token=token,
        )
        self.assertEqual(features_res.code, 200)
        self.assertEqual(len(features_res.json_body["features"]), 1)

        # First spend succeeds.
        spend_res = self.make_request(
            "POST",
            "/_matrix/client/v3/mcredits/spend",
            {"feature_key": "voip_premium"},
            access_token=token,
        )
        self.assertEqual(spend_res.code, 200)
        self.assertEqual(spend_res.json_body["balance"], 300)

        # Balance endpoint reflects remaining credits.
        balance_res = self.make_request(
            "GET",
            "/_matrix/client/v3/mcredits/balance",
            access_token=token,
        )
        self.assertEqual(balance_res.code, 200)
        self.assertEqual(balance_res.json_body["balance"], 300)

        # Second spend fails due to insufficient credits.
        second_spend_res = self.make_request(
            "POST",
            "/_matrix/client/v3/mcredits/spend",
            {"feature_key": "voip_premium"},
            access_token=token,
        )
        self.assertEqual(second_spend_res.code, 402)

        # Ensure a debit transaction exists.
        tx_rows = self.get_success(
            self.store.db_pool.simple_select_list(
                table="mcredit_transactions",
                keyvalues={"user_id": user_id, "reason": "voip_premium"},
                retcols=("amount",),
                desc="test_mcredits_full_flow_tx_rows",
            )
        )
        self.assertEqual(len(tx_rows), 1)
        self.assertEqual(tx_rows[0][0], -700)
