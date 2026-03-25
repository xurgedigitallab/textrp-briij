#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.core.binarycodec import decode as decode_tx_blob, encode_for_signing
from xrpl.core.keypairs import derive_classic_address, is_valid_message

from textrp_briij.api.errors import Codes, LoginError, SynapseError
from textrp_briij.auth.wallet_chain_adapter import WalletChainAdapter

logger = logging.getLogger(__name__)


class XrplChainAdapter(WalletChainAdapter):
    LOGIN_TYPE = "io.briij.login.xrpl"
    SESSION_TYPE = "xrpl_auth"
    SUPPORTED_NETWORKS = ("xrpl", "xahau")

    def chain_id(self) -> str:
        return "xrpl"

    def login_type(self) -> str:
        return self.LOGIN_TYPE

    def session_type(self) -> str:
        return self.SESSION_TYPE

    def is_initial_request(self, login_submission: dict[str, Any]) -> bool:
        return "session" not in login_submission and "signature" not in login_submission

    def validate_account_id(self, account_id: Any) -> str:
        if not isinstance(account_id, str) or not account_id:
            raise SynapseError(400, "Missing address", Codes.MISSING_PARAM)
        if not is_valid_classic_address(account_id):
            raise SynapseError(400, "Invalid XRPL classic address", Codes.INVALID_PARAM)
        return account_id

    def validate_network(self, network: Any) -> str:
        if not isinstance(network, str) or not network:
            raise SynapseError(400, "Missing network", Codes.MISSING_PARAM)

        normalized_network = network.lower()
        if normalized_network not in self.SUPPORTED_NETWORKS:
            raise SynapseError(400, "Unsupported XRPL network", Codes.INVALID_PARAM)
        return normalized_network

    def build_challenge(
        self,
        account_id: str,
        *,
        issued_at_ms: int,
        nonce: str,
    ) -> str:
        issued_at = datetime.fromtimestamp(
            issued_at_ms / 1000,
            tz=timezone.utc,
        ).replace(microsecond=0)
        return (
            f"textrp-briij|{issued_at.isoformat().replace('+00:00', 'Z')}"
            f"|nonce:{nonce}|{account_id}"
        )

    def verify_login_proof(
        self,
        *,
        account_id: str,
        challenge: str,
        signature: str,
        public_key: str | None,
    ) -> str:
        signin_public_key = self._try_verify_signin_tx(
            signature_hex=signature,
            account_id=account_id,
        )
        if signin_public_key is not None:
            return signin_public_key

        if not isinstance(public_key, str) or not public_key:
            raise SynapseError(
                400,
                "Missing public_key for XRPL login",
                Codes.MISSING_PARAM,
            )

        self._verify_signature(
            account_id=account_id,
            challenge=challenge,
            signature=signature,
            public_key=public_key,
        )
        return public_key

    def _try_verify_signin_tx(
        self,
        *,
        signature_hex: str,
        account_id: str,
    ) -> str | None:
        """If signature_hex is a signed XRPL SignIn transaction for this address,
        verify it and return the signer's public key (hex). Otherwise return None.
        """
        try:
            sig_bytes = bytes.fromhex(signature_hex)
        except ValueError:
            logger.debug("XRPL login: signature is not valid hex")
            return None
        if len(sig_bytes) < 32:
            return None
        try:
            decoded = decode_tx_blob(signature_hex)
        except Exception as e:
            logger.debug(
                "XRPL login: SignIn/decode failed (client may have sent Xaman SignIn blob): %s",
                e,
            )
            return None
        if not isinstance(decoded, dict):
            return None
        tx_account = decoded.get("Account")
        if not isinstance(tx_account, str) or tx_account != account_id:
            if isinstance(tx_account, str):
                logger.debug(
                    "XRPL login: SignIn Account %s does not match requested %s",
                    tx_account,
                    account_id,
                )
            return None
        signing_pub_key = decoded.get("SigningPubKey")
        txn_sig = decoded.get("TxnSignature")
        if not signing_pub_key or not txn_sig:
            return None
        if isinstance(signing_pub_key, bytes):
            signing_pub_key = signing_pub_key.hex()
        if isinstance(txn_sig, bytes):
            txn_sig = txn_sig.hex()
        try:
            to_sign_hex = encode_for_signing(decoded)
            to_sign_bytes = bytes.fromhex(to_sign_hex)
            txn_sig_bytes = bytes.fromhex(txn_sig)
            key_upper = (
                signing_pub_key.upper()
                if isinstance(signing_pub_key, str)
                else signing_pub_key
            )
            if not is_valid_message(to_sign_bytes, txn_sig_bytes, key_upper):
                logger.debug("XRPL login: SignIn signature verification failed")
                return None
        except Exception as e:
            logger.debug("XRPL login: SignIn verify exception: %s", e)
            return None
        return (
            signing_pub_key
            if isinstance(signing_pub_key, str)
            else signing_pub_key.hex()
        )

    def _verify_signature(
        self,
        *,
        account_id: str,
        challenge: str,
        signature: str,
        public_key: str,
    ) -> None:
        try:
            signature_bytes = bytes.fromhex(signature)
        except ValueError:
            raise LoginError(
                403,
                "XRPL signature must be hexadecimal",
                errcode=Codes.INVALID_SIGNATURE,
            )

        normalized_public_key = public_key.upper()
        try:
            derived_address = derive_classic_address(normalized_public_key)
        except Exception as e:
            raise SynapseError(400, "Invalid XRPL public key", Codes.INVALID_PARAM) from e

        if derived_address != account_id:
            raise LoginError(
                403,
                "XRPL public key does not match the requested address",
                errcode=Codes.FORBIDDEN,
            )

        message_bytes = challenge.encode("utf-8")
        key_hex: str | None = None
        if (
            len(normalized_public_key) == 64
            and all(c in "0123456789ABCDEF" for c in normalized_public_key)
        ):
            key_hex = normalized_public_key
        elif (
            normalized_public_key.startswith("ED")
            and len(normalized_public_key) == 66
            and all(c in "0123456789ABCDEF" for c in normalized_public_key[2:])
        ):
            key_hex = normalized_public_key[2:]

        if key_hex is not None:
            try:
                pub_bytes = bytes.fromhex(key_hex)
                if len(pub_bytes) != 32:
                    raise LoginError(
                        403,
                        "XRPL signature verification failed",
                        errcode=Codes.INVALID_SIGNATURE,
                    )
                ed_pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
                ed_pub.verify(signature_bytes, message_bytes)
            except (ValueError, InvalidSignature) as e:
                raise LoginError(
                    403,
                    "XRPL signature verification failed",
                    errcode=Codes.INVALID_SIGNATURE,
                ) from e
        else:
            if not is_valid_message(message_bytes, signature_bytes, normalized_public_key):
                raise LoginError(
                    403,
                    "XRPL signature verification failed",
                    errcode=Codes.INVALID_SIGNATURE,
                )
