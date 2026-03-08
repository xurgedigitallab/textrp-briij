from __future__ import annotations

from typing import Any

from textrp_briij.module_api import ModuleApi
from textrp_briij.types import JsonDict


class WalletProvider:
    LOGIN_TYPE = "io.briij.login.xrpl"
    LOGIN_FIELDS = ("wallet_address", "signature", "challenge")

    def __init__(self, config: JsonDict, api: ModuleApi):
        self._config = config
        self._api = api

        api.register_password_auth_provider_callbacks(
            auth_checkers={(self.LOGIN_TYPE, self.LOGIN_FIELDS): self.check_auth}
        )

    @staticmethod
    def parse_config(config: JsonDict) -> JsonDict:
        return config

    def get_supported_login_types(self) -> dict[str, list[str]]:
        return {self.LOGIN_TYPE: list(self.LOGIN_FIELDS)}

    async def check_auth(
        self, username: str, login_type: str, login_dict: JsonDict
    ) -> Any:
        raise NotImplementedError
