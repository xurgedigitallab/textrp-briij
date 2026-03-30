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

from textrp_briij.scripts.seed_mcredits_features import seed_premium_features
from textrp_briij.api.errors import SynapseError
from textrp_briij.server import HomeServer
from textrp_briij.util.clock import Clock

from tests.unittest import HomeserverTestCase


class MCreditStoreTestCase(HomeserverTestCase):
    def prepare(self, reactor: MemoryReactor, clock: Clock, hs: HomeServer) -> None:
        self.store = hs.get_datastores().main
        self.user_id = "@mcredit-user:test"
        self.get_success(self.store.register_user(self.user_id, None))

    def test_initial_balance_after_insert(self) -> None:
        self.get_success(
            self.store.db_pool.simple_insert(
                "mcredit_balances",
                {
                    "user_id": self.user_id,
                    "balance": 1000,
                    "updated_ts": self.clock.time_msec(),
                },
                desc="test_initial_balance_after_insert",
            )
        )

        balance = self.get_success(self.store.get_mcredit_balance(self.user_id))
        self.assertEqual(balance, 1000)

    def test_feature_lookup(self) -> None:
        self.get_success(
            self.store.db_pool.simple_insert(
                "premium_features",
                {
                    "feature_id": 1,
                    "feature_key": "voip_premium",
                    "name": "VoIP Premium",
                    "description": "Premium voice service",
                    "mcredits_cost": 100,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="test_feature_lookup",
            )
        )

        feature = self.get_success(self.store.get_premium_feature_by_key("voip_premium"))
        self.assertIsNotNone(feature)
        assert feature is not None
        self.assertEqual(feature["feature_id"], 1)
        self.assertEqual(feature["mcredits_cost"], 100)

    def test_successful_spend_reduces_balance(self) -> None:
        self.get_success(
            self.store.db_pool.simple_insert(
                "mcredit_balances",
                {
                    "user_id": self.user_id,
                    "balance": 1000,
                    "updated_ts": self.clock.time_msec(),
                },
                desc="test_successful_spend_balance",
            )
        )
        self.get_success(
            self.store.db_pool.simple_insert(
                "premium_features",
                {
                    "feature_id": 2,
                    "feature_key": "teleconference_hd",
                    "name": "Teleconference HD",
                    "description": "HD conferencing",
                    "mcredits_cost": 250,
                    "category": "communication",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="test_successful_spend_feature",
            )
        )

        new_balance = self.get_success(
            self.store.spend_mcredits(
                self.user_id,
                "teleconference_hd",
                amount=250,
                reason="teleconference_hd",
            )
        )
        self.assertEqual(new_balance, 750)

        balance = self.get_success(self.store.get_mcredit_balance(self.user_id))
        self.assertEqual(balance, 750)

    def test_insufficient_balance_raises_402(self) -> None:
        self.get_success(
            self.store.db_pool.simple_insert(
                "mcredit_balances",
                {
                    "user_id": self.user_id,
                    "balance": 50,
                    "updated_ts": self.clock.time_msec(),
                },
                desc="test_insufficient_balance_balance",
            )
        )
        self.get_success(
            self.store.db_pool.simple_insert(
                "premium_features",
                {
                    "feature_id": 3,
                    "feature_key": "media_high_res",
                    "name": "Media High Res",
                    "description": "High resolution media",
                    "mcredits_cost": 100,
                    "category": "media",
                    "is_active": True,
                    "created_ts": self.clock.time_msec(),
                },
                desc="test_insufficient_balance_feature",
            )
        )

        failure = self.get_failure(
            self.store.spend_mcredits(
                self.user_id,
                "media_high_res",
                amount=100,
                reason="media_high_res",
            ),
            SynapseError,
        )
        self.assertEqual(failure.value.code, 402)

    def test_seed_premium_features(self) -> None:
        seeded = self.get_success(
            seed_premium_features(self.store, self.clock.time_msec())
        )
        self.assertEqual(seeded, 4)

        rows = self.get_success(
            self.store.db_pool.simple_select_list(
                table="premium_features",
                keyvalues={},
                retcols=("feature_key", "mcredits_cost"),
                desc="test_seeded_features",
            )
        )
        self.assertEqual(len(rows), 4)
