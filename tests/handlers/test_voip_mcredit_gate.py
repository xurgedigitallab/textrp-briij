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


class VoipMCreditGateTestCase(HomeserverTestCase):
    def prepare(self, reactor: MemoryReactor, clock: Clock, hs: HomeServer) -> None:
        self.store = hs.get_datastores().main
        self.voip_handler = hs.get_voip_handler()
        self.user_id = "@voip-gate-user:test"
        self.get_success(self.store.register_user(self.user_id, None))
        self.get_success(
            self.store.db_pool.simple_insert(
                "mcredit_balances",
                {
                    "user_id": self.user_id,
                    "balance": 300,
                    "updated_ts": self.clock.time_msec(),
                },
                desc="test_voip_gate_insert_balance",
            )
        )
        self.get_success(
            self.store.db_pool.simple_insert(
                "premium_features",
                {
                    "feature_id": 500,
                    "feature_key": "voip_premium",
                    "name": "VoIP Premium",
                    "description": "Premium voice calls",
                    "mcredits_cost": 200,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="test_voip_gate_insert_feature",
            )
        )

    def test_voip_gate_spends_then_blocks_when_insufficient(self) -> None:
        requester = create_requester(self.user_id)

        first = self.get_success(self.voip_handler.start_call(requester))
        self.assertTrue(first["started"])
        self.assertEqual(first["balance"], 100)

        failure = self.get_failure(self.voip_handler.start_call(requester), SynapseError)
        self.assertEqual(failure.value.code, 402)
