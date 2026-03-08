# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 TextRP https://textrp.io
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from xrpl.clients import JsonRpcClient

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


_XRPL_JSON_RPC_BY_NETWORK = {
    "mainnet": "https://s1.ripple.com:51234",
    "testnet": "https://s.altnet.rippletest.net:51234",
}


class XrplIdentityHandler:
    """Native XRPL primitives for identity flows in Synapse handlers."""

    def __init__(self, hs: "HomeServer"):
        self._hs = hs
        network = os.environ.get("XRPL_NETWORK", "testnet").strip().lower()
        self._network = network if network in _XRPL_JSON_RPC_BY_NETWORK else "testnet"
        self._json_rpc_url = os.environ.get(
            "XRPL_JSON_RPC_URL",
            _XRPL_JSON_RPC_BY_NETWORK[self._network],
        ).strip()
        self._client = JsonRpcClient(self._json_rpc_url)

    @property
    def network(self) -> str:
        return self._network

    @property
    def json_rpc_url(self) -> str:
        return self._json_rpc_url

    async def get_client(self) -> JsonRpcClient:
        return self._client
