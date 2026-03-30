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
    existing_count = await store.db_pool.simple_select_one_onecol(
        table="premium_features",
        keyvalues={},
        retcol="COUNT(*)",
        allow_none=False,
        desc="count_premium_features",
    )
    if int(existing_count) > 0:
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
        await store.db_pool.simple_insert(
            "premium_features",
            {
                "feature_id": feature_id,
                "feature_key": feature_key,
                "name": name,
                "description": description,
                "mcredits_cost": mcredits_cost,
                "category": category,
                "is_active": True,
                "created_ts": now_ms,
            },
            desc=f"seed_{feature_key}",
        )
        seeded += 1

    return seeded
