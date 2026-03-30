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

from textrp_briij.api.errors import SynapseError
from textrp_briij.server import HomeServer
from textrp_briij.types import create_requester
from textrp_briij.util.clock import Clock

from tests.unittest import HomeserverTestCase


class MCreditHandlerTestCase(HomeserverTestCase):
    def prepare(self, reactor: MemoryReactor, clock: Clock, hs: HomeServer) -> None:
        self.store = hs.get_datastores().main
        self.handler = hs.get_mcredit_handler()
        self.user_id = "@mcredit_handler_user:test"
        self.get_success(self.store.register_user(self.user_id, None))
        self.get_success(
            self.store.db_pool.simple_insert(
                "mcredit_balances",
                {
                    "user_id": self.user_id,
                    "balance": 1000,
                    "updated_ts": self.clock.time_msec(),
                },
                desc="test_mcredit_handler_insert_balance",
            )
        )

    def test_spend_mcredits_success(self) -> None:
        self.get_success(
            self.store.db_pool.simple_insert(
                "premium_features",
                {
                    "feature_id": 101,
                    "feature_key": "voip_premium",
                    "name": "VoIP Premium",
                    "description": "Premium voice calls",
                    "mcredits_cost": 200,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="test_spend_mcredits_success_insert_feature",
            )
        )

        requester = create_requester(self.user_id)
        new_balance = self.get_success(
            self.handler.spend_mcredits(requester, feature_key="voip_premium")
        )
        self.assertEqual(new_balance, 800)

    def test_spend_mcredits_unknown_feature(self) -> None:
        requester = create_requester(self.user_id)
        failure = self.get_failure(
            self.handler.spend_mcredits(requester, feature_key="unknown_feature"),
            SynapseError,
        )
        self.assertEqual(failure.value.code, 404)

    def test_spend_mcredits_insufficient_balance(self) -> None:
        self.get_success(
            self.store.db_pool.simple_insert(
                "premium_features",
                {
                    "feature_id": 102,
                    "feature_key": "teleconference_hd",
                    "name": "Teleconference HD",
                    "description": "HD conferencing",
                    "mcredits_cost": 2000,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="test_spend_mcredits_insufficient_balance_insert_feature",
            )
        )

        requester = create_requester(self.user_id)
        failure = self.get_failure(
            self.handler.spend_mcredits(requester, feature_key="teleconference_hd"),
            SynapseError,
        )
        self.assertEqual(failure.value.code, 402)
