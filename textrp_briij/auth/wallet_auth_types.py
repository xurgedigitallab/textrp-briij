#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

from typing import TypedDict

from textrp_briij.types import JsonDict

WALLET_IDENTITY_ACCOUNT_DATA_TYPE = "org.textrp.wallet.identity"
WALLET_E2EE_RECOVERY_ACCOUNT_DATA_TYPE = "org.textrp.wallet.e2ee_recovery.v1"
XRPL_WALLET_ACCOUNT_DATA_TYPE = "org.textrp.xrpl.wallet"


class WalletIdentity(TypedDict):
    chain_id: str
    account_id: str
    public_key: str | None
    network: str | None
    key_type: str | None


def build_wallet_identity_payload(
    *,
    chain_id: str,
    account_id: str,
    public_key: str | None,
    network: str | None = None,
    key_type: str | None = None,
) -> JsonDict:
    return {
        "chain_id": chain_id,
        "account_id": account_id,
        "public_key": public_key,
        "network": network,
        "key_type": key_type,
    }
