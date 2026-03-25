#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

from typing import Any, Protocol

from textrp_briij.types import JsonDict


class WalletChainAdapter(Protocol):
    def chain_id(self) -> str: ...

    def login_type(self) -> str: ...

    def session_type(self) -> str: ...

    def is_initial_request(self, login_submission: JsonDict) -> bool: ...

    def validate_account_id(self, account_id: Any) -> str: ...

    def validate_network(self, network: Any) -> str: ...

    def build_challenge(
        self,
        account_id: str,
        *,
        issued_at_ms: int,
        nonce: str,
    ) -> str: ...

    def verify_login_proof(
        self,
        *,
        account_id: str,
        challenge: str,
        signature: str,
        public_key: str | None,
    ) -> str: ...
