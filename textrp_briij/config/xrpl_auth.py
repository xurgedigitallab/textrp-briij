#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

from textwrap import dedent
from typing import Any

from textrp_briij.types import JsonDict

from ._base import Config, ConfigError


class XrplAuthConfig(Config):
    section = "xrpl_auth"

    def read_config(self, config: JsonDict, **kwargs: Any) -> None:
        xrpl_auth_config = config.get("xrpl_auth") or {}

        if not isinstance(xrpl_auth_config, dict):
            raise ConfigError("xrpl_auth must be a mapping", ("xrpl_auth",))

        self.enabled = xrpl_auth_config.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ConfigError("xrpl_auth.enabled must be a boolean", ("xrpl_auth", "enabled"))

        self.allow_account_creation = xrpl_auth_config.get(
            "allow_account_creation",
            True,
        )
        if not isinstance(self.allow_account_creation, bool):
            raise ConfigError(
                "xrpl_auth.allow_account_creation must be a boolean",
                ("xrpl_auth", "allow_account_creation"),
            )

        self.xrpl_node_url = xrpl_auth_config.get(
            "xrpl_node_url",
            "https://s.altnet.rippletest.net:51234",
        )
        if not isinstance(self.xrpl_node_url, str):
            raise ConfigError(
                "xrpl_auth.xrpl_node_url must be a string",
                ("xrpl_auth", "xrpl_node_url"),
            )

        self.xahau_node_url = xrpl_auth_config.get(
            "xahau_node_url",
            "https://xahau-testnet.xrpl-labs.com",
        )
        if not isinstance(self.xahau_node_url, str):
            raise ConfigError(
                "xrpl_auth.xahau_node_url must be a string",
                ("xrpl_auth", "xahau_node_url"),
            )

        challenge_ttl_seconds = xrpl_auth_config.get("challenge_ttl_seconds", 300)
        if not isinstance(challenge_ttl_seconds, int):
            raise ConfigError(
                "xrpl_auth.challenge_ttl_seconds must be an integer",
                ("xrpl_auth", "challenge_ttl_seconds"),
            )
        if challenge_ttl_seconds <= 0:
            raise ConfigError(
                "xrpl_auth.challenge_ttl_seconds must be greater than zero",
                ("xrpl_auth", "challenge_ttl_seconds"),
            )

        self.challenge_ttl_seconds = challenge_ttl_seconds
        self.challenge_ttl_ms = challenge_ttl_seconds * 1000

    def generate_config_section(self, **kwargs: Any) -> str:
        return dedent(
            """
            # Native XRPL/Xahau wallet authentication.
            #
            # When enabled, clients can use the custom Matrix login type
            # `io.briij.login.xrpl` to request a signed challenge and complete
            # login using a locally-held XRPL or Xahau seed.
            #
            #xrpl_auth:
            #  enabled: true
            #  allow_account_creation: true
            #  xrpl_node_url: "https://s.altnet.rippletest.net:51234"
            #  xahau_node_url: "https://xahau-testnet.xrpl-labs.com"
            #  challenge_ttl_seconds: 300
            """
        )
