from typing import Any
import json

from twisted.internet import defer
from twisted.web.resource import Resource

from synapse.handlers.mcredits_store import McreditsStore
from synapse.api.errors import SynapseError
from synapse.module_api import ModuleApi
from synapse.http.server import respond_with_json, NOT_DONE_YET


class CreditsResource(Resource):
    """Public endpoint: GET /_briij/credits returns available packages"""

    isLeaf = True

    def __init__(self, store: McreditsStore):
        super().__init__()
        self.store = store

    def render_GET(self, request):
        defer.ensureDeferred(self._async_render_get(request))
        return NOT_DONE_YET  # Twisted async pattern

    async def _async_render_get(self, request):
        packages = await self.store.get_active_packages()
        respond_with_json(request, 200, packages)


class AdminPackagesResource(Resource):
    """Admin CRUD for mcredit packages: GET/POST/PUT/DELETE"""

    isLeaf = True

    def __init__(self, store: McreditsStore, api: ModuleApi):
        super().__init__()
        self.store = store
        self.api = api

    def render_GET(self, request):
        defer.ensureDeferred(self._async_render_get(request))
        return NOT_DONE_YET

    async def _async_render_get(self, request):
        # Only admins allowed
        requester = await self.api.get_user_by_req(request)
        if not await self.api.is_user_admin(requester.user.to_string()):
            raise SynapseError(403, "Admin access required")

        packages = await self.store.get_all_packages()  # we will add this method next
        respond_with_json(request, 200, packages)

    def render_POST(self, request):
        defer.ensureDeferred(self._async_render_post(request))
        return NOT_DONE_YET

    async def _async_render_post(self, request):
        requester = await self.api.get_user_by_req(request)
        if not await self.api.is_user_admin(requester.user.to_string()):
            raise SynapseError(403, "Admin access required")

        content = json.loads(request.content.read().decode("utf-8"))
        package_id = await self.store.create_or_update_package(content)
        respond_with_json(request, 200, {"id": package_id, "status": "ok"})


class McreditsModule:
    def __init__(self, config: dict, api: ModuleApi):
        self.api = api

        main_store = (
            api.get_datastores().main
            if hasattr(api, "get_datastores")
            else api._hs.get_datastores().main
        )
        self.store: McreditsStore = McreditsStore(main_store.db_pool)

        # Register the public packages endpoint
        self.api.register_web_resource("/_briij/credits", CreditsResource(self.store))
        self.api.register_web_resource(
            "/_briij/admin/credits/packages",
            AdminPackagesResource(self.store, self.api),
        )

    @staticmethod
    def parse_config(config: dict) -> Any:
        return config
