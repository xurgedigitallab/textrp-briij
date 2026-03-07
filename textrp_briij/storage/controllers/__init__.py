#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright 2022 The Matrix.org Foundation C.I.C.
# Copyright (C) 2023 New Vector, Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Originally licensed under the Apache License, Version 2.0:
# <http://www.apache.org/licenses/LICENSE-2.0>.
#
# [This file includes modifications made by New Vector Limited]
#
#

from typing import TYPE_CHECKING

from textrp_briij.storage.controllers.persist_events import (
    EventsPersistenceStorageController,
)
from textrp_briij.storage.controllers.purge_events import PurgeEventsStorageController
from textrp_briij.storage.controllers.state import StateStorageController
from textrp_briij.storage.controllers.stats import StatsController
from textrp_briij.storage.databases import Databases
from textrp_briij.storage.databases.main import DataStore

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


__all__ = ["Databases", "DataStore"]


class StorageControllers:
    """The high level interfaces for talking to various storage controller layers."""

    def __init__(self, hs: "HomeServer", stores: Databases):
        # We include the main data store here mainly so that we don't have to
        # rewrite all the existing code to split it into high vs low level
        # interfaces.
        self.main = stores.main

        self.purge_events = PurgeEventsStorageController(hs, stores)
        self.state = StateStorageController(hs, stores)
        self.stats = StatsController(hs, stores)

        self.persistence = None
        if stores.persist_events:
            self.persistence = EventsPersistenceStorageController(
                hs, stores, self.state
            )
