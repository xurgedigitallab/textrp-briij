#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 TextRP https://textrp.io
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
from unittest import TestCase

from textrp_briij.handlers.verification import (
    decode_xrpl_uri,
    extract_verifiers_from_metadata,
)


class VerificationNftMetadataTests(TestCase):
    def test_decode_xrpl_uri_handles_hex_encoded_uri(self) -> None:
        self.assertEqual(
            decode_xrpl_uri("697066733A2F2F6261667962656967"),
            "ipfs://bafybeig",
        )

    def test_extract_verifiers_from_metadata_normalizes_addresses(self) -> None:
        metadata = {
            "verifiers": [
                "rEXAMPLEAddress111111111111111111",
                "  rAnotherAddress222222222222222  ",
                "",
                7,
            ]
        }
        self.assertEqual(
            extract_verifiers_from_metadata(metadata),
            {
                "rexampleaddress111111111111111111",
                "ranotheraddress222222222222222",
            },
        )
