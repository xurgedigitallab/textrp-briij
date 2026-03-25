#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

import base64
import binascii
from typing import Any

from textrp_briij.api.errors import Codes, SynapseError
from textrp_briij.types import JsonDict

MAX_RECOVERY_ENVELOPE_LENGTH = 16_384
SUPPORTED_RECOVERY_ENVELOPE_VERSION = 1


def _assert_base64_str(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise SynapseError(
            400,
            f"Invalid wallet_e2ee_recovery.{name}",
            Codes.INVALID_PARAM,
        )
    try:
        base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise SynapseError(
            400,
            f"wallet_e2ee_recovery.{name} must be base64",
            Codes.INVALID_PARAM,
        )
    return value


def _assert_string(name: str, value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise SynapseError(
            400,
            f"Invalid wallet_e2ee_recovery.{name}",
            Codes.INVALID_PARAM,
        )
    if not allow_empty and not value:
        raise SynapseError(
            400,
            f"Invalid wallet_e2ee_recovery.{name}",
            Codes.INVALID_PARAM,
        )
    return value


def _assert_positive_int(name: str, value: Any) -> int:
    if not isinstance(value, int) or value < 0:
        raise SynapseError(
            400,
            f"Invalid wallet_e2ee_recovery.{name}",
            Codes.INVALID_PARAM,
        )
    return value


def _validate_wrap(kind: str, value: Any) -> JsonDict:
    if not isinstance(value, dict):
        raise SynapseError(
            400,
            f"wallet_e2ee_recovery.{kind} must be an object",
            Codes.INVALID_PARAM,
        )

    _assert_string(f"{kind}.alg", value.get("alg"))
    _assert_string(f"{kind}.kdf", value.get("kdf"))
    _assert_base64_str(f"{kind}.salt", value.get("salt"))
    _assert_base64_str(f"{kind}.nonce", value.get("nonce"))
    _assert_base64_str(f"{kind}.ciphertext", value.get("ciphertext"))
    if value.get("aad") is not None:
        _assert_base64_str(f"{kind}.aad", value.get("aad"))
    params = value.get("params")
    if params is not None and not isinstance(params, dict):
        raise SynapseError(
            400,
            f"wallet_e2ee_recovery.{kind}.params must be an object",
            Codes.INVALID_PARAM,
        )
    return value


def validate_wallet_recovery_envelope(
    envelope: Any,
    *,
    expected_chain_id: str,
    expected_account_id: str,
) -> JsonDict:
    if envelope is None:
        raise SynapseError(
            400,
            "wallet_e2ee_recovery cannot be null",
            Codes.INVALID_PARAM,
        )
    if not isinstance(envelope, dict):
        raise SynapseError(
            400,
            "wallet_e2ee_recovery must be an object",
            Codes.INVALID_PARAM,
        )

    if len(str(envelope)) > MAX_RECOVERY_ENVELOPE_LENGTH:
        raise SynapseError(
            400,
            "wallet_e2ee_recovery is too large",
            Codes.INVALID_PARAM,
        )

    envelope_version = envelope.get("envelope_version")
    if envelope_version != SUPPORTED_RECOVERY_ENVELOPE_VERSION:
        raise SynapseError(
            400,
            "Unsupported wallet_e2ee_recovery.envelope_version",
            Codes.INVALID_PARAM,
        )

    chain_id = _assert_string("chain_id", envelope.get("chain_id"))
    account_id = _assert_string("account_id", envelope.get("account_id"))
    if chain_id != expected_chain_id or account_id != expected_account_id:
        raise SynapseError(
            400,
            "wallet_e2ee_recovery identity does not match authenticated wallet",
            Codes.INVALID_PARAM,
        )

    created_at_ms = _assert_positive_int("created_at_ms", envelope.get("created_at_ms"))
    key_id = _assert_string("key_id", envelope.get("key_id"))

    wallet_wrap = _validate_wrap("wallet_wrap", envelope.get("wallet_wrap"))
    password_wrap = _validate_wrap("password_wrap", envelope.get("password_wrap"))

    return {
        "envelope_version": envelope_version,
        "chain_id": chain_id,
        "account_id": account_id,
        "created_at_ms": created_at_ms,
        "key_id": key_id,
        "wallet_wrap": wallet_wrap,
        "password_wrap": password_wrap,
    }
