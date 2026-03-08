#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from typing import TYPE_CHECKING

from textrp_briij.http.server import DirectServeJsonResource
from textrp_briij.http.site import SynapseRequest
from textrp_briij.types import JsonDict

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


class BriijInfoResource(DirectServeJsonResource):
    """AGPL-3.0 §13 source repository disclosure endpoint."""

    def __init__(self, hs: "HomeServer"):
        super().__init__(clock=hs.get_clock())

    async def _async_render_GET(self, request: SynapseRequest) -> tuple[int, JsonDict]:
        return (
            200,
            {
                "source_repository": "https://github.com/xurgedigitallab/textrp-briij",
                "license": "AGPL-3.0-or-later",
                "license_url": "https://www.gnu.org/licenses/agpl-3.0.html",
            },
        )
