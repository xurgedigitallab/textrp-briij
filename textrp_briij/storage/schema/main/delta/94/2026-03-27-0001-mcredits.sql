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

-- User balances (one row per user, created on registration)
CREATE TABLE mcredit_balances (
    user_id TEXT PRIMARY KEY REFERENCES users(name) ON DELETE CASCADE,
    balance BIGINT NOT NULL DEFAULT 1000,
    updated_ts BIGINT NOT NULL DEFAULT 0
);

-- Premium feature catalog (extendable forever)
CREATE TABLE premium_features (
    feature_id INTEGER PRIMARY KEY,
    feature_key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    mcredits_cost INTEGER NOT NULL CHECK (mcredits_cost > 0),
    category TEXT,
    is_active BOOLEAN DEFAULT true,
    created_ts BIGINT NOT NULL DEFAULT 0
);

-- Audit trail (required for compliance + on-chain reconciliation)
CREATE TABLE mcredit_transactions (
    tx_id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES mcredit_balances(user_id) ON DELETE CASCADE,
    feature_id INTEGER REFERENCES premium_features(feature_id),
    amount BIGINT NOT NULL,
    reason TEXT NOT NULL,
    onchain_tx_id TEXT,
    ts BIGINT NOT NULL DEFAULT 0
);

-- Indexes for speed
CREATE INDEX idx_mcredit_transactions_user_ts ON mcredit_transactions(user_id, ts DESC);
CREATE INDEX idx_premium_features_key ON premium_features(feature_key);
