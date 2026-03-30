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

from textrp_briij.server import HomeServer
from textrp_briij.util.clock import Clock

from tests.unittest import HomeserverTestCase


class MCreditRegistrationTestCase(HomeserverTestCase):
    def prepare(self, reactor: MemoryReactor, clock: Clock, hs: HomeServer) -> None:
        self.registration_handler = hs.get_registration_handler()
        self.store = hs.get_datastores().main

    def test_new_user_gets_initial_mcredits(self) -> None:
        user_id = self.get_success(
            self.registration_handler.register_user(localpart="mcredit_alice")
        )

        balance = self.get_success(self.store.get_mcredit_balance(user_id))
        self.assertEqual(balance, 1000)

    def test_initial_balance_and_transaction_exist(self) -> None:
        user_id = self.get_success(
            self.registration_handler.register_user(localpart="mcredit_bob")
        )

        balance_row = self.get_success(
            self.store.db_pool.simple_select_one(
                table="mcredit_balances",
                keyvalues={"user_id": user_id},
                retcols=("user_id", "balance"),
                desc="test_mcredit_balance_row",
            )
        )
        self.assertEqual(balance_row[1], 1000)

        tx_rows = self.get_success(
            self.store.db_pool.simple_select_list(
                table="mcredit_transactions",
                keyvalues={"user_id": user_id, "reason": "initial_bonus"},
                retcols=("amount", "reason"),
                desc="test_mcredit_initial_tx",
            )
        )
        self.assertEqual(len(tx_rows), 1)
        self.assertEqual(tx_rows[0][0], 1000)
