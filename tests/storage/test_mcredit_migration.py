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

from textrp_briij.storage.database import LoggingDatabaseConnection
from textrp_briij.storage.engines import PostgresEngine
from textrp_briij.storage.prepare_database import prepare_database

from tests.unittest import HomeserverTestCase


class MCreditMigrationTestCase(HomeserverTestCase):
    def test_mcredit_migration_creates_expected_schema(self) -> None:
        db_pool = self.hs.get_datastores().main.db_pool
        db_conn = LoggingDatabaseConnection(
            conn=db_pool._db_pool.connect(),
            engine=db_pool.engine,
            default_txn_name="tests",
            server_name="test_server",
        )

        cur = db_conn.cursor()

        # Force this specific migration to be re-applied by prepare_database.
        cur.execute("DROP TABLE IF EXISTS mcredit_transactions")
        cur.execute("DROP TABLE IF EXISTS premium_features")
        cur.execute("DROP TABLE IF EXISTS mcredit_balances")
        cur.execute(
            "DELETE FROM applied_schema_deltas WHERE version = ? AND file = ?",
            (94, "94/2026-03-27-0001-mcredits.sql"),
        )
        cur.execute("UPDATE schema_version SET version = ?, upgraded = ?", (94, True))
        db_conn.commit()

        prepare_database(db_conn, db_pool.engine, self.hs.config)

        if isinstance(db_pool.engine, PostgresEngine):
            self._assert_postgres_schema(db_conn)
        else:
            self._assert_sqlite_schema(db_conn)

    def _assert_postgres_schema(self, db_conn: LoggingDatabaseConnection) -> None:
        cur = db_conn.cursor()
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                'mcredit_balances',
                'premium_features',
                'mcredit_transactions'
              )
            ORDER BY table_name
            """
        )
        self.assertEqual(
            [row[0] for row in cur.fetchall()],
            ["mcredit_balances", "mcredit_transactions", "premium_features"],
        )

        cur.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN (
                'mcredit_balances',
                'premium_features',
                'mcredit_transactions'
              )
            """
        )
        columns = {(row[0], row[1]): row[2] for row in cur.fetchall()}
        self.assertEqual(columns[("mcredit_balances", "user_id")], "text")
        self.assertEqual(columns[("mcredit_balances", "balance")], "bigint")
        self.assertEqual(columns[("mcredit_balances", "updated_ts")], "bigint")
        self.assertEqual(columns[("premium_features", "feature_id")], "integer")
        self.assertEqual(columns[("premium_features", "feature_key")], "text")
        self.assertEqual(columns[("premium_features", "name")], "text")
        self.assertEqual(columns[("premium_features", "description")], "text")
        self.assertEqual(columns[("premium_features", "mcredits_cost")], "integer")
        self.assertEqual(columns[("premium_features", "category")], "text")
        self.assertEqual(columns[("premium_features", "is_active")], "boolean")
        self.assertEqual(columns[("premium_features", "created_ts")], "bigint")
        self.assertEqual(columns[("mcredit_transactions", "tx_id")], "bigint")
        self.assertEqual(columns[("mcredit_transactions", "user_id")], "text")
        self.assertEqual(columns[("mcredit_transactions", "feature_id")], "integer")
        self.assertEqual(columns[("mcredit_transactions", "amount")], "bigint")
        self.assertEqual(columns[("mcredit_transactions", "reason")], "text")
        self.assertEqual(columns[("mcredit_transactions", "onchain_tx_id")], "text")
        self.assertEqual(columns[("mcredit_transactions", "ts")], "bigint")

        cur.execute(
            """
            SELECT indexname, tablename, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname IN (
                'idx_mcredit_transactions_user_ts',
                'idx_premium_features_key'
              )
            ORDER BY indexname
            """
        )
        index_rows = cur.fetchall()
        self.assertEqual(len(index_rows), 2)
        index_by_name = {row[0]: row for row in index_rows}
        self.assertEqual(index_by_name["idx_premium_features_key"][1], "premium_features")
        self.assertIn("(feature_key)", index_by_name["idx_premium_features_key"][2])
        self.assertEqual(
            index_by_name["idx_mcredit_transactions_user_ts"][1], "mcredit_transactions"
        )
        self.assertIn(
            "(user_id, ts DESC)", index_by_name["idx_mcredit_transactions_user_ts"][2]
        )

        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS condef
            FROM pg_constraint
            WHERE contype = 'f'
              AND conrelid::regclass::text IN (
                'mcredit_balances',
                'mcredit_transactions'
              )
            """
        )
        fk_defs = [row[0] for row in cur.fetchall()]
        self.assertTrue(
            any(
                "FOREIGN KEY (user_id) REFERENCES users(name) ON DELETE CASCADE"
                in fk
                for fk in fk_defs
            )
        )
        self.assertTrue(
            any(
                "FOREIGN KEY (user_id) REFERENCES mcredit_balances(user_id) ON DELETE CASCADE"
                in fk
                for fk in fk_defs
            )
        )
        self.assertTrue(
            any(
                "FOREIGN KEY (feature_id) REFERENCES premium_features(feature_id)" in fk
                for fk in fk_defs
            )
        )

    def _assert_sqlite_schema(self, db_conn: LoggingDatabaseConnection) -> None:
        cur = db_conn.cursor()
        cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN ('mcredit_balances', 'premium_features', 'mcredit_transactions')
            ORDER BY name
            """
        )
        self.assertEqual(
            [row[0] for row in cur.fetchall()],
            ["mcredit_balances", "mcredit_transactions", "premium_features"],
        )

        expected_columns = {
            "mcredit_balances": {"user_id", "balance", "updated_ts"},
            "premium_features": {
                "feature_id",
                "feature_key",
                "name",
                "description",
                "mcredits_cost",
                "category",
                "is_active",
                "created_ts",
            },
            "mcredit_transactions": {
                "tx_id",
                "user_id",
                "feature_id",
                "amount",
                "reason",
                "onchain_tx_id",
                "ts",
            },
        }
        for table, expected in expected_columns.items():
            cur.execute(f"PRAGMA table_info({table})")
            present = {row[1] for row in cur.fetchall()}
            self.assertEqual(present, expected)

        cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
              AND name IN (
                'idx_mcredit_transactions_user_ts',
                'idx_premium_features_key'
              )
            ORDER BY name
            """
        )
        self.assertEqual(
            [row[0] for row in cur.fetchall()],
            ["idx_mcredit_transactions_user_ts", "idx_premium_features_key"],
        )

        cur.execute("PRAGMA foreign_key_list(mcredit_balances)")
        balances_fks = {(row[2], row[3], row[4], row[6]) for row in cur.fetchall()}
        self.assertIn(("users", "user_id", "name", "CASCADE"), balances_fks)

        cur.execute("PRAGMA foreign_key_list(mcredit_transactions)")
        tx_fks = {(row[2], row[3], row[4], row[6]) for row in cur.fetchall()}
        self.assertIn(
            ("mcredit_balances", "user_id", "user_id", "CASCADE"),
            tx_fks,
        )
        self.assertIn(("premium_features", "feature_id", "feature_id", "NO ACTION"), tx_fks)
