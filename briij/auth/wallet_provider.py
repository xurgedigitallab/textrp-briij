from __future__ import annotations

from typing import Any

import xrpl.clients as xrpl_clients
from xrpl.asyncio.clients import AsyncJsonRpcClient as XrplAsyncJsonRpcClient

from textrp_briij.module_api import ModuleApi
from textrp_briij.types import JsonDict

AsyncJsonRpcClient = getattr(
    xrpl_clients, "AsyncJsonRpcClient", XrplAsyncJsonRpcClient
)


class WalletProvider:
    LOGIN_TYPE = "io.briij.login.xrpl"
    LOGIN_FIELDS = ("wallet_address", "signature", "challenge", "network")
    SUPPORTED_NETWORKS = ("xrpl", "xahau")

    def __init__(self, config: JsonDict, api: ModuleApi):
        self._config = self.parse_config(config)
        self._api = api
        self.allowed_networks = tuple(
            str(network) for network in self._config["allowed_networks"]
        )
        self.default_network = str(self._config["default_network"])
        self.jsonrpc_urls_by_network = {
            network: tuple(
                str(url)
                for url in self._config[network]["jsonrpc_urls"]  # type: ignore[index]
            )
            for network in self.allowed_networks
        }
        self.clients_by_network = {
            network: AsyncJsonRpcClient(self.jsonrpc_urls_by_network[network][0])
            for network in self.allowed_networks
        }

        api.register_password_auth_provider_callbacks(
            auth_checkers={(self.LOGIN_TYPE, self.LOGIN_FIELDS): self.check_auth}
        )

    @staticmethod
    def parse_config(config: JsonDict) -> JsonDict:
        normalized: JsonDict = {}

        allowed_networks_value = config.get("allowed_networks")
        if isinstance(allowed_networks_value, list):
            allowed_networks = [str(network) for network in allowed_networks_value]
        else:
            allowed_networks = ["xrpl", "xahau"]

        default_network_value = config.get("default_network")
        if isinstance(default_network_value, str):
            default_network = default_network_value
        else:
            default_network = "xrpl"

        normalized["allowed_networks"] = allowed_networks
        normalized["default_network"] = default_network

        for network in WalletProvider.SUPPORTED_NETWORKS:
            network_config_value = config.get(network)
            network_config: JsonDict = (
                dict(network_config_value)
                if isinstance(network_config_value, dict)
                else {}
            )

            urls_value = network_config.get("jsonrpc_urls")
            if isinstance(urls_value, list):
                jsonrpc_urls = [str(url) for url in urls_value]
            else:
                fallback_url = network_config.get("jsonrpc_url")
                if isinstance(fallback_url, str):
                    jsonrpc_urls = [fallback_url]
                else:
                    jsonrpc_urls = []

            normalized[network] = {"jsonrpc_urls": jsonrpc_urls}

        return normalized

    def get_supported_login_types(self) -> dict[str, list[str]]:
        return {self.LOGIN_TYPE: list(self.LOGIN_FIELDS)}

    async def check_auth(
        self, username: str, login_type: str, login_dict: JsonDict
    ) -> Any:
        raise NotImplementedError
