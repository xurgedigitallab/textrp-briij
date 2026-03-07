#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright 2020 The Matrix.org Foundation C.I.C.
# Copyright 2016 OpenMarket Ltd
# Copyright (C) 2023-2024 New Vector, Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Originally licensed under the Apache License, Version 2.0:
# <http://www.apache.org/licenses/LICENSE-2.0>.
#
# [This file includes modifications made by New Vector Limited]
#
#
import logging
import sys
from typing import Optional

from twisted.web.resource import Resource

import textrp_briij
import textrp_briij.events
from textrp_briij.api.urls import (
    CLIENT_API_PREFIX,
    FEDERATION_PREFIX,
    LEGACY_MEDIA_PREFIX,
    MEDIA_R0_PREFIX,
    MEDIA_V3_PREFIX,
    SERVER_KEY_PREFIX,
)
from textrp_briij.app import _base
from textrp_briij.app._base import (
    handle_startup_exception,
    max_request_body_size,
    redirect_stdio_to_logs,
    register_start,
)
from textrp_briij.config._base import ConfigError
from textrp_briij.config.homeserver import HomeServerConfig
from textrp_briij.config.logger import setup_logging
from textrp_briij.config.server import ListenerConfig, TCPListenerConfig
from textrp_briij.federation.transport.server import TransportLayerServer
from textrp_briij.http.server import JsonResource, OptionsResource
from textrp_briij.logging.context import LoggingContext
from textrp_briij.logging.opentracing import init_tracer
from textrp_briij.metrics import METRICS_PREFIX, MetricsResource, RegistryProxy
from textrp_briij.replication.http import REPLICATION_PREFIX, ReplicationRestResource
from textrp_briij.rest import ClientRestResource, admin
from textrp_briij.rest.health import HealthResource
from textrp_briij.rest.key.v2 import KeyResource
from textrp_briij.rest.briij.client import build_briij_client_resource_tree
from textrp_briij.rest.well_known import well_known_resource
from textrp_briij.server import HomeServer
from textrp_briij.storage.databases.main.account_data import AccountDataWorkerStore
from textrp_briij.storage.databases.main.appservice import (
    ApplicationServiceTransactionWorkerStore,
    ApplicationServiceWorkerStore,
)
from textrp_briij.storage.databases.main.censor_events import CensorEventsStore
from textrp_briij.storage.databases.main.client_ips import ClientIpWorkerStore
from textrp_briij.storage.databases.main.delayed_events import DelayedEventsStore
from textrp_briij.storage.databases.main.deviceinbox import DeviceInboxWorkerStore
from textrp_briij.storage.databases.main.devices import DeviceWorkerStore
from textrp_briij.storage.databases.main.directory import DirectoryWorkerStore
from textrp_briij.storage.databases.main.e2e_room_keys import EndToEndRoomKeyStore
from textrp_briij.storage.databases.main.event_federation import EventFederationWorkerStore
from textrp_briij.storage.databases.main.event_push_actions import (
    EventPushActionsWorkerStore,
)
from textrp_briij.storage.databases.main.events_worker import EventsWorkerStore
from textrp_briij.storage.databases.main.experimental_features import (
    ExperimentalFeaturesStore,
)
from textrp_briij.storage.databases.main.filtering import FilteringWorkerStore
from textrp_briij.storage.databases.main.keys import KeyStore
from textrp_briij.storage.databases.main.lock import LockStore
from textrp_briij.storage.databases.main.media_repository import MediaRepositoryStore
from textrp_briij.storage.databases.main.metrics import ServerMetricsStore
from textrp_briij.storage.databases.main.monthly_active_users import (
    MonthlyActiveUsersWorkerStore,
)
from textrp_briij.storage.databases.main.presence import PresenceStore
from textrp_briij.storage.databases.main.profile import ProfileWorkerStore
from textrp_briij.storage.databases.main.purge_events import PurgeEventsStore
from textrp_briij.storage.databases.main.push_rule import PushRulesWorkerStore
from textrp_briij.storage.databases.main.pusher import PusherWorkerStore
from textrp_briij.storage.databases.main.receipts import ReceiptsWorkerStore
from textrp_briij.storage.databases.main.registration import RegistrationWorkerStore
from textrp_briij.storage.databases.main.relations import RelationsWorkerStore
from textrp_briij.storage.databases.main.room import RoomWorkerStore
from textrp_briij.storage.databases.main.roommember import RoomMemberWorkerStore
from textrp_briij.storage.databases.main.search import SearchStore
from textrp_briij.storage.databases.main.session import SessionStore
from textrp_briij.storage.databases.main.signatures import SignatureWorkerStore
from textrp_briij.storage.databases.main.sliding_sync import SlidingSyncStore
from textrp_briij.storage.databases.main.state import StateGroupWorkerStore
from textrp_briij.storage.databases.main.stats import StatsStore
from textrp_briij.storage.databases.main.sticky_events import StickyEventsWorkerStore
from textrp_briij.storage.databases.main.stream import StreamWorkerStore
from textrp_briij.storage.databases.main.tags import TagsWorkerStore
from textrp_briij.storage.databases.main.task_scheduler import TaskSchedulerWorkerStore
from textrp_briij.storage.databases.main.thread_subscriptions import (
    ThreadSubscriptionsWorkerStore,
)
from textrp_briij.storage.databases.main.transactions import TransactionWorkerStore
from textrp_briij.storage.databases.main.ui_auth import UIAuthWorkerStore
from textrp_briij.storage.databases.main.user_directory import UserDirectoryStore
from textrp_briij.storage.databases.main.user_erasure_store import UserErasureWorkerStore
from textrp_briij.types import IBriijReactor
from textrp_briij.util.httpresourcetree import create_resource_tree

logger = logging.getLogger("textrp_briij.app.generic_worker")


class GenericWorkerStore(
    # FIXME(https://github.com/matrix-org/synapse/issues/3714): We need to add
    # UserDirectoryStore as we write directly rather than going via the correct worker.
    UserDirectoryStore,
    UIAuthWorkerStore,
    EndToEndRoomKeyStore,
    PresenceStore,
    DeviceInboxWorkerStore,
    DeviceWorkerStore,
    TagsWorkerStore,
    AccountDataWorkerStore,
    CensorEventsStore,
    ClientIpWorkerStore,
    # KeyStore isn't really safe to use from a worker, but for now we do so and hope that
    # the races it creates aren't too bad.
    KeyStore,
    RoomWorkerStore,
    DirectoryWorkerStore,
    ThreadSubscriptionsWorkerStore,
    StickyEventsWorkerStore,
    PushRulesWorkerStore,
    ApplicationServiceTransactionWorkerStore,
    ApplicationServiceWorkerStore,
    ProfileWorkerStore,
    FilteringWorkerStore,
    MonthlyActiveUsersWorkerStore,
    MediaRepositoryStore,
    ServerMetricsStore,
    PusherWorkerStore,
    RoomMemberWorkerStore,
    RelationsWorkerStore,
    EventFederationWorkerStore,
    EventPushActionsWorkerStore,
    PurgeEventsStore,
    StateGroupWorkerStore,
    SignatureWorkerStore,
    UserErasureWorkerStore,
    ReceiptsWorkerStore,
    StreamWorkerStore,
    EventsWorkerStore,
    RegistrationWorkerStore,
    StatsStore,
    SearchStore,
    TransactionWorkerStore,
    LockStore,
    SessionStore,
    TaskSchedulerWorkerStore,
    ExperimentalFeaturesStore,
    SlidingSyncStore,
    DelayedEventsStore,
):
    # Properties that multiple storage classes define. Tell mypy what the
    # expected type is.
    server_name: str
    config: HomeServerConfig


class GenericWorkerServer(HomeServer):
    DATASTORE_CLASS = GenericWorkerStore

    def _listen_http(self, listener_config: ListenerConfig) -> None:
        assert listener_config.http_options is not None

        # We always include an admin resource that we populate with servlets as needed
        admin_resource = JsonResource(self, canonical_json=False)
        resources: dict[str, Resource] = {
            # We always include a health resource.
            "/health": HealthResource(),
            "/_briij/admin": admin_resource,
        }

        for res in listener_config.http_options.resources:
            for name in res.names:
                if name == "metrics":
                    resources[METRICS_PREFIX] = MetricsResource(RegistryProxy)
                elif name == "client":
                    resource: Resource = ClientRestResource(self)

                    resources[CLIENT_API_PREFIX] = resource

                    resources.update(build_briij_client_resource_tree(self))
                    resources["/.well-known"] = well_known_resource(self)
                    admin.register_servlets(self, admin_resource)

                elif name == "federation":
                    resources[FEDERATION_PREFIX] = TransportLayerServer(self)
                elif name == "media":
                    if self.config.media.can_load_media_repo:
                        media_repo = self.get_media_repository_resource()

                        # We need to serve the admin servlets for media on the
                        # worker.
                        admin.register_servlets_for_media_repo(self, admin_resource)

                        resources.update(
                            {
                                MEDIA_R0_PREFIX: media_repo,
                                MEDIA_V3_PREFIX: media_repo,
                                LEGACY_MEDIA_PREFIX: media_repo,
                            }
                        )

                        if "federation" not in res.names:
                            # Only load the federation media resource separately if federation
                            # resource is not specified since federation resource includes media
                            # resource.
                            resources[FEDERATION_PREFIX] = TransportLayerServer(
                                self, servlet_groups=["media"]
                            )
                        if "client" not in res.names:
                            # Only load the client media resource separately if client
                            # resource is not specified since client resource includes media
                            # resource.
                            resources[CLIENT_API_PREFIX] = ClientRestResource(
                                self, servlet_groups=["media"]
                            )
                    else:
                        logger.warning(
                            "A 'media' listener is configured but the media"
                            " repository is disabled. Ignoring."
                        )
                elif name == "health":
                    # Skip loading, health resource is always included
                    continue

                if name == "openid" and "federation" not in res.names:
                    # Only load the openid resource separately if federation resource
                    # is not specified since federation resource includes openid
                    # resource.
                    resources[FEDERATION_PREFIX] = TransportLayerServer(
                        self, servlet_groups=["openid"]
                    )

                if name in ["keys", "federation"]:
                    resources[SERVER_KEY_PREFIX] = KeyResource(self)

                if name == "replication":
                    resources[REPLICATION_PREFIX] = ReplicationRestResource(self)

        # Attach additional resources registered by modules.
        resources.update(self._module_web_resources)
        self._module_web_resources_consumed = True

        root_resource = create_resource_tree(resources, OptionsResource())

        _base.listen_http(
            self,
            listener_config,
            root_resource,
            self.version_string,
            max_request_body_size(self.config),
            self.tls_server_context_factory,
            reactor=self.get_reactor(),
        )

    def start_listening(self) -> None:
        for listener in self.config.worker.worker_listeners:
            if listener.type == "http":
                self._listen_http(listener)
            elif listener.type == "manhole":
                if isinstance(listener, TCPListenerConfig):
                    self._listening_services.extend(
                        _base.listen_manhole(
                            listener.bind_addresses,
                            listener.port,
                            manhole_settings=self.config.server.manhole_settings,
                            manhole_globals={"hs": self},
                        )
                    )
                else:
                    raise ConfigError(
                        "Can not using a unix socket for manhole at this time."
                    )

            elif listener.type == "metrics":
                if not self.config.metrics.enable_metrics:
                    logger.warning(
                        "Metrics listener configured, but enable_metrics is not True!"
                    )
                else:
                    if isinstance(listener, TCPListenerConfig):
                        self._metrics_listeners.extend(
                            _base.listen_metrics(
                                listener.bind_addresses,
                                listener.port,
                            )
                        )
                    else:
                        raise ConfigError(
                            "Can not use a unix socket for metrics at this time."
                        )

            else:
                logger.warning("Unsupported listener type: %s", listener.type)

        self.get_replication_command_handler().start_replication(self)


def load_config(argv_options: list[str]) -> HomeServerConfig:
    """
    Parse the commandline and config files (does not generate config)

    Args:
        argv_options: The options passed to Briij. Usually `sys.argv[1:]`.

    Returns:
        Config object.
    """
    try:
        config = HomeServerConfig.load_config("Briij worker", argv_options)
    except ConfigError as e:
        sys.stderr.write("\n" + str(e) + "\n")
        sys.exit(1)

    return config


def create_homeserver(
    config: HomeServerConfig,
    reactor: Optional[IBriijReactor] = None,
) -> GenericWorkerServer:
    """
    Create a homeserver instance for the Briij worker process.

    Our composable functions (`create_homeserver`, `setup`, `start`) should not exit the
    Python process (call `exit(...)`) and instead raise exceptions which can be handled
    by the caller as desired. This doesn't matter for the normal case of one Briij
    instance running in the Python process (as we're only affecting ourselves), but is
    important when we have multiple Briij homeserver tenants running in the same
    Python process (c.f. Briij Pro for small hosts) as we don't want some problem from
    one tenant stopping the rest of the tenants.

    Args:
        config: The configuration for the homeserver.
        reactor: Optionally provide a reactor to use. Can be useful in different
            scenarios that you want control over the reactor, such as tests.

    Returns:
        A homeserver instance.
    """

    # For backwards compatibility let any of the old app names.
    assert config.worker.worker_app in (
        "textrp_briij.app.appservice",
        "textrp_briij.app.client_reader",
        "textrp_briij.app.event_creator",
        "textrp_briij.app.federation_reader",
        "textrp_briij.app.federation_sender",
        "textrp_briij.app.frontend_proxy",
        "textrp_briij.app.generic_worker",
        "textrp_briij.app.media_repository",
        "textrp_briij.app.pusher",
        "textrp_briij.app.synchrotron",
        "textrp_briij.app.user_dir",
    )

    textrp_briij.events.USE_FROZEN_DICTS = config.server.use_frozen_dicts
    textrp_briij.util.caches.TRACK_MEMORY_USAGE = config.caches.track_memory_usage

    if config.server.gc_seconds:
        textrp_briij.metrics.MIN_TIME_BETWEEN_GCS = config.server.gc_seconds

    hs = GenericWorkerServer(
        config.server.server_name,
        config=config,
        reactor=reactor,
    )

    return hs


def setup(hs: GenericWorkerServer) -> None:
    """
    Setup a `GenericWorkerServer` (worker) instance.

    Our composable functions (`create_homeserver`, `setup`, `start`) should not exit the
    Python process (call `exit(...)`) and instead raise exceptions which can be handled
    by the caller as desired. This doesn't matter for the normal case of one Synapse
    instance running in the Python process (as we're only affecting ourselves), but is
    important when we have multiple Synapse homeserver tenants running in the same
    Python process (c.f. Synapse Pro for small hosts) as we don't want some problem from
    one tenant stopping the rest of the tenants.

    Args:
        hs: The homeserver to setup.
    """

    setup_logging(hs, hs.config, use_worker_options=True)

    # Start the tracer
    init_tracer(hs)  # noqa

    hs.setup()

    # Ensure the replication streamer is always started in case we write to any
    # streams. Will no-op if no streams can be written to by this worker.
    hs.get_replication_streamer()


async def start(
    hs: GenericWorkerServer,
    *,
    freeze: bool = True,
) -> None:
    """
    Should be called once the reactor is running.

    Our composable functions (`create_homeserver`, `setup`, `start`) should not exit the
    Python process (call `exit(...)`) and instead raise exceptions which can be handled
    by the caller as desired. This doesn't matter for the normal case of one Synapse
    instance running in the Python process (as we're only affecting ourselves), but is
    important when we have multiple Synapse homeserver tenants running in the same
    Python process (c.f. Synapse Pro for small hosts) as we don't want some problem from
    one tenant stopping the rest of the tenants.

    Args:
        hs: The homeserver to setup.
        freeze: whether to freeze the homeserver base objects in the garbage collector.
            May improve garbage collection performance by marking objects with an effectively
            static lifetime as frozen so they don't need to be considered for cleanup.
            If you ever want to `shutdown` the homeserver, this needs to be
            False otherwise the homeserver cannot be garbage collected after `shutdown`.
    """

    await _base.start(hs, freeze=freeze)


def main() -> None:
    homeserver_config = load_config(sys.argv[1:])

    # Create a logging context as soon as possible so we can start associating
    # everything with this homeserver.
    with LoggingContext(name="main", server_name=homeserver_config.server.server_name):
        # Initialize and setup the homeserver
        hs = create_homeserver(homeserver_config)
        try:
            setup(hs)
        except Exception as e:
            handle_startup_exception(e)

        # For problems immediately apparent during initialization, we want to log to
        # stderr in the terminal so that they are obvious and visible to the operator.
        #
        # Now that we're past the initialization stage, we can redirect anything printed
        # to stdio to the logs, if configured.
        if not homeserver_config.logging.no_redirect_stdio:
            redirect_stdio_to_logs()

        # Register a callback to be invoked once the reactor is running
        register_start(hs, start, hs)

        _base.start_worker_reactor("briij-generic-worker", homeserver_config)


if __name__ == "__main__":
    main()
