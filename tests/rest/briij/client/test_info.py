#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.

from twisted.web.resource import Resource

from textrp_briij.rest.briij.client import build_briij_client_resource_tree

from tests import unittest


class BriijInfoTests(unittest.HomeserverTestCase):
    def create_resource_dict(self) -> dict[str, Resource]:
        base = super().create_resource_dict()
        base.update(build_briij_client_resource_tree(self.hs))
        return base

    def test_info_endpoint(self) -> None:
        channel = self.make_request("GET", "/_briij/info", shorthand=False)

        self.assertEqual(channel.code, 200)
        self.assertEqual(
            channel.json_body,
            {
                "source_repository": "https://github.com/xurgedigitallab/textrp-briij",
                "license": "AGPL-3.0-or-later",
                "license_url": "https://www.gnu.org/licenses/agpl-3.0.html",
            },
        )
