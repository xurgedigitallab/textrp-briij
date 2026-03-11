--
-- This file is licensed under the Affero General Public License (AGPL) version 3.
--
-- Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
--
-- See the GNU Affero General Public License for more details:
-- <https://www.gnu.org/licenses/agpl-3.0.html>.

ALTER TABLE briij_wallet_links
    ADD COLUMN public_key TEXT;
