from typing import Any
import json

from textrp_briij.api.errors import SynapseError
from textrp_briij.module_api import ModuleApi
from textrp_briij.http.server import DirectServeJsonResource


class McreditsStore:
    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def get_active_packages(self) -> list[dict]:
        rows = await self.db_pool.execute(
            "mcredits_get_active_packages",
            """
            SELECT id, name, description, credits_amount, price_usd_cents, sort_order
            FROM mcredit_packages
            WHERE is_active = true
            ORDER BY sort_order ASC
            """,
        )
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "credits_amount": row[3],
                "price_usd_cents": row[4],
                "sort_order": row[5],
            }
            for row in rows
        ]

    async def get_all_packages(self) -> list[dict]:
        rows = await self.db_pool.execute(
            "mcredits_get_all_packages",
            """
            SELECT id, name, description, credits_amount, price_usd_cents, sort_order, is_active
            FROM mcredit_packages
            ORDER BY sort_order ASC, id ASC
            """,
        )
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "credits_amount": row[3],
                "price_usd_cents": row[4],
                "sort_order": row[5],
                "is_active": bool(row[6]),
            }
            for row in rows
        ]

    async def create_or_update_package(self, data: dict) -> int:
        name = data["name"]
        description = data.get("description")
        credits_amount = data["credits_amount"]
        price_usd_cents = data["price_usd_cents"]
        sort_order = data.get("sort_order", 0)
        is_active = data.get("is_active", True)
        package_id = data.get("id")

        if package_id:
            await self.db_pool.execute(
                "mcredits_update_package",
                """
                UPDATE mcredit_packages
                SET name = %s, description = %s, credits_amount = %s,
                    price_usd_cents = %s, sort_order = %s, is_active = %s,
                    updated_ts = EXTRACT(EPOCH FROM NOW())::bigint
                WHERE id = %s
                """,
                (
                    name,
                    description,
                    credits_amount,
                    price_usd_cents,
                    sort_order,
                    is_active,
                    package_id,
                ),
            )
            return package_id

        row = await self.db_pool.execute(
            "mcredits_insert_package",
            """
            INSERT INTO mcredit_packages (name, description, credits_amount, price_usd_cents, sort_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (name, description, credits_amount, price_usd_cents, sort_order, is_active),
        )
        return row[0][0]


class CreditsResource(DirectServeJsonResource):
    """Public endpoint: GET /_briij/credits returns available packages"""

    isLeaf = True

    def __init__(self, store: McreditsStore):
        super().__init__()
        self.store = store

    async def _async_render_GET(self, request):
        packages = await self.store.get_active_packages()
        return 200, packages


class AdminPackagesResource(DirectServeJsonResource):
    """Admin endpoint: GET/POST /_briij/admin/credits/packages"""

    isLeaf = True

    def __init__(self, store: McreditsStore, api: ModuleApi):
        super().__init__()
        self.store = store
        self.api = api

    async def _assert_admin(self, request) -> None:
        requester = await self.api.get_user_by_req(request)
        if not await self.api.is_user_admin(requester.user.to_string()):
            raise SynapseError(403, "Admin access required")

    async def _async_render_GET(self, request):
        await self._assert_admin(request)
        packages = await self.store.get_all_packages()
        return 200, packages

    async def _async_render_POST(self, request):
        await self._assert_admin(request)
        body = json.loads(request.content.read().decode("utf-8"))
        package_id = await self.store.create_or_update_package(body)
        return 200, {"id": package_id, "status": "ok"}


class McreditsModule:
    def __init__(self, config: dict, api: ModuleApi):
        self.api = api

        # Get or create the mcredits store (Synapse will inject db_pool etc.)
        self.store = McreditsStore(api._hs.get_datastores().main.db_pool)  # or however your existing mcredits store is instantiated

        # Register the public packages endpoint
        self.api.register_web_resource(
            "/_briij/credits",
            CreditsResource(self.store),
        )
        admin_resource = AdminPackagesResource(self.store, self.api)
        self.api.register_web_resource("/_briij/admin/credits/packages", admin_resource)
        self.api.register_web_resource("/_briij/admin/v2/briij/credits/packages", admin_resource)

    @staticmethod
    def parse_config(config: dict) -> Any:
        # Minimal config for now
        return config
