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

from typing import TYPE_CHECKING

from textrp_briij.storage.engines import PostgresEngine, Sqlite3Engine

if TYPE_CHECKING:
    from textrp_briij.storage.databases.main import DataStore


PREMIUM_FEATURES: tuple[tuple[int, str, str, str, int, str], ...] = (
    (1, "voip_premium", "VoIP Premium", "Premium voice call quality", 200, "communication"),
    (
        2,
        "teleconference_hd",
        "Teleconference HD",
        "HD teleconference quality",
        300,
        "communication",
    ),
    (
        3,
        "media_high_res",
        "Media High Resolution",
        "High resolution media delivery",
        150,
        "media",
    ),
    (4, "ai_summary", "AI Summary", "Automated AI call summary", 100, "monetization"),
)


async def seed_premium_features(store: "DataStore", now_ms: int) -> int:
    def _table_exists_txn(txn) -> bool:
        if isinstance(store.database_engine, PostgresEngine):
            txn.execute("SELECT to_regclass('public.premium_features')")
            row = txn.fetchone()
            return row is not None and row[0] is not None

        if isinstance(store.database_engine, Sqlite3Engine):
            txn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'premium_features'
                """
            )
            return txn.fetchone() is not None

        return False

    table_exists = await store.db_pool.runInteraction(
        "check_premium_features_table_exists", _table_exists_txn
    )
    if not table_exists:
        return 0

    seeded = 0
    for (
        feature_id,
        feature_key,
        name,
        description,
        mcredits_cost,
        category,
    ) in PREMIUM_FEATURES:
        inserted = await store.db_pool.simple_upsert(
            table="premium_features",
            keyvalues={"feature_key": feature_key},
            values={},
            insertion_values={
                "feature_id": feature_id,
                "name": name,
                "description": description,
                "mcredits_cost": mcredits_cost,
                "category": category,
                "is_active": True,
                "created_ts": now_ms,
            },
            desc=f"seed_{feature_key}",
        )
        if inserted:
            seeded += 1

    return seeded
