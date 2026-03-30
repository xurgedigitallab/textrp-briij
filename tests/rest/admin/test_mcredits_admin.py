#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 Xurge Digital Lab
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#

from twisted.internet.testing import MemoryReactor

import textrp_briij.rest.admin
from textrp_briij.api.errors import Codes
from textrp_briij.rest.client import login
from textrp_briij.server import HomeServer
from textrp_briij.util.clock import Clock

from tests import unittest


class MCreditsAdminRestTestCase(unittest.HomeserverTestCase):
    servlets = [
        textrp_briij.rest.admin.register_servlets,
        login.register_servlets,
    ]

    def prepare(self, reactor: MemoryReactor, clock: Clock, hs: HomeServer) -> None:
        self.admin_user = self.register_user("admin", "pass", admin=True)
        self.admin_token = self.login("admin", "pass")

        self.user = self.register_user("user", "pass")
        self.user_token = self.login("user", "pass")

        self.collection_url = "/_synapse/admin/v2/briij/premium_features"

    def test_admin_crud_cycle(self) -> None:
        create_res = self.make_request(
            "POST",
            self.collection_url,
            {
                "feature_key": "custom_feature",
                "name": "Custom Feature",
                "description": "Initial description",
                "mcredits_cost": 55,
                "category": "communication",
            },
            access_token=self.admin_token,
        )
        self.assertEqual(200, create_res.code, msg=create_res.json_body)
        self.assertEqual("custom_feature", create_res.json_body["feature_key"])
        self.assertEqual(55, create_res.json_body["mcredits_cost"])
        self.assertTrue(create_res.json_body["is_active"])

        list_res = self.make_request(
            "GET", self.collection_url, access_token=self.admin_token
        )
        self.assertEqual(200, list_res.code, msg=list_res.json_body)
        self.assertTrue(
            any(
                f["feature_key"] == "custom_feature"
                for f in list_res.json_body["premium_features"]
            )
        )

        update_res = self.make_request(
            "PUT",
            self.collection_url + "/custom_feature",
            {
                "mcredits_cost": 75,
                "description": "Updated description",
                "is_active": True,
            },
            access_token=self.admin_token,
        )
        self.assertEqual(200, update_res.code, msg=update_res.json_body)
        self.assertEqual(75, update_res.json_body["mcredits_cost"])
        self.assertEqual("Updated description", update_res.json_body["description"])
        self.assertTrue(update_res.json_body["is_active"])

        delete_res = self.make_request(
            "DELETE",
            self.collection_url + "/custom_feature",
            access_token=self.admin_token,
        )
        self.assertEqual(200, delete_res.code, msg=delete_res.json_body)
        self.assertFalse(delete_res.json_body["is_active"])

    def test_non_admin_forbidden(self) -> None:
        # Seed one feature so PUT/DELETE target an existing record.
        self.make_request(
            "POST",
            self.collection_url,
            {
                "feature_key": "admin_only",
                "name": "Admin Only",
                "description": "Only admins can mutate",
                "mcredits_cost": 25,
                "category": "communication",
            },
            access_token=self.admin_token,
        )

        requests = [
            ("GET", self.collection_url, None),
            (
                "POST",
                self.collection_url,
                {
                    "feature_key": "forbidden_create",
                    "name": "Forbidden",
                    "description": "Forbidden",
                    "mcredits_cost": 10,
                    "category": "communication",
                },
            ),
            (
                "PUT",
                self.collection_url + "/admin_only",
                {"mcredits_cost": 30, "is_active": True},
            ),
            ("DELETE", self.collection_url + "/admin_only", None),
        ]

        for method, url, body in requests:
            channel = self.make_request(
                method,
                url,
                content=body if body is not None else {},
                access_token=self.user_token,
            )
            self.assertEqual(403, channel.code, msg=channel.json_body)
            self.assertEqual(Codes.FORBIDDEN, channel.json_body["errcode"])

    def test_create_cost_must_be_positive(self) -> None:
        channel = self.make_request(
            "POST",
            self.collection_url,
            {
                "feature_key": "invalid_cost_feature",
                "name": "Invalid",
                "description": "Invalid cost",
                "mcredits_cost": 0,
                "category": "communication",
            },
            access_token=self.admin_token,
        )
        self.assertEqual(400, channel.code, msg=channel.json_body)
        self.assertEqual(Codes.INVALID_PARAM, channel.json_body["errcode"])

    def test_update_cost_must_be_positive(self) -> None:
        create_res = self.make_request(
            "POST",
            self.collection_url,
            {
                "feature_key": "updatable_feature",
                "name": "Updatable",
                "description": "Updatable cost",
                "mcredits_cost": 40,
                "category": "communication",
            },
            access_token=self.admin_token,
        )
        self.assertEqual(200, create_res.code, msg=create_res.json_body)

        update_res = self.make_request(
            "PUT",
            self.collection_url + "/updatable_feature",
            {"mcredits_cost": -1},
            access_token=self.admin_token,
        )
        self.assertEqual(400, update_res.code, msg=update_res.json_body)
        self.assertEqual(Codes.INVALID_PARAM, update_res.json_body["errcode"])
