--
-- This file is licensed under the Affero General Public License (AGPL) version 3.
--
-- Copyright (C) 2026 Xurge Digital Lab
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU Affero General Public License as
-- published by the Free Software Foundation, either version 3 of the
-- License, or (at your option) any later version.
--
-- See the GNU Affero General Public License for more details:
-- <https://www.gnu.org/licenses/agpl-3.0.html>.

CREATE TABLE IF NOT EXISTS briij_wallet_links (
    user_id TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    network TEXT NOT NULL,
    linked_at BIGINT NOT NULL,
    UNIQUE(wallet_address, network)
);
