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

from textrp_briij.api.errors import Codes, SynapseError
from textrp_briij.types import Requester

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


class MCreditHandler:
    def __init__(self, hs: "HomeServer"):
        self.store = hs.get_datastores().main

    async def spend_mcredits(self, requester: Requester, feature_key: str) -> int:
        user_id = requester.user.to_string()
        feature = await self.store.get_premium_feature_by_key(feature_key)
        if feature is None:
            raise SynapseError(404, "Premium feature not found", errcode=Codes.NOT_FOUND)

        amount = int(feature["mcredits_cost"])
        return await self.store.spend_mcredits(
            user_id=user_id,
            feature_key=feature_key,
            amount=amount,
            reason=feature_key,
        )
