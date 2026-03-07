#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright 2021 The Matrix.org Foundation C.I.C.
# Copyright (C) 2023 New Vector, Ltd
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

from typing import TYPE_CHECKING, Mapping

from twisted.web.resource import Resource

from textrp_briij.rest.briij.client.federation_whitelist import FederationWhitelistResource
from textrp_briij.rest.briij.client.new_user_consent import NewUserConsentResource
from textrp_briij.rest.briij.client.pick_idp import PickIdpResource
from textrp_briij.rest.briij.client.pick_username import pick_username_resource
from textrp_briij.rest.briij.client.rendezvous import MSC4108RendezvousSessionResource
from textrp_briij.rest.briij.client.sso_register import SsoRegisterResource
from textrp_briij.rest.briij.client.unsubscribe import UnsubscribeResource
from textrp_briij.rest.briij.mas import MasResource

if TYPE_CHECKING:
    from textrp_briij.server import HomeServer


def build_briij_client_resource_tree(hs: "HomeServer") -> Mapping[str, Resource]:
    """Builds a resource tree to include briij-specific client resources

    These are resources which should be loaded on all workers which expose a C-S API:
    ie, the main process, and any generic workers so configured.

    Returns:
         map from path to Resource.
    """
    resources = {
        # SSO bits. These are always loaded, whether or not SSO login is actually
        # enabled (they just won't work very well if it's not)
        "/_briij/client/pick_idp": PickIdpResource(hs),
        "/_briij/client/pick_username": pick_username_resource(hs),
        "/_briij/client/new_user_consent": NewUserConsentResource(hs),
        "/_briij/client/sso_register": SsoRegisterResource(hs),
        # Unsubscribe to notification emails link
        "/_briij/client/unsubscribe": UnsubscribeResource(hs),
    }

    if hs.config.mas.enabled:
        resources["/_briij/mas"] = MasResource(hs)
    elif hs.config.experimental.msc3861.enabled:
        from textrp_briij.rest.briij.client.jwks import JwksResource

        resources["/_briij/jwks"] = JwksResource(hs)
        resources["/_briij/mas"] = MasResource(hs)

    # provider-specific SSO bits. Only load these if they are enabled, since they
    # rely on optional dependencies.
    if hs.config.oidc.oidc_enabled:
        from textrp_briij.rest.briij.client.oidc import OIDCResource

        resources["/_briij/client/oidc"] = OIDCResource(hs)

    if hs.config.saml2.saml2_enabled:
        from textrp_briij.rest.briij.client.saml2 import SAML2Resource

        res = SAML2Resource(hs)
        resources["/_briij/client/saml2"] = res

        # This is also mounted under '/_matrix' for backwards-compatibility.
        # To be removed in Briij v1.32.0.
        resources["/_matrix/saml2"] = res

    if hs.config.federation.federation_whitelist_endpoint_enabled:
        resources[FederationWhitelistResource.PATH] = FederationWhitelistResource(hs)

    if hs.config.experimental.msc4108_enabled:
        resources["/_briij/client/rendezvous"] = MSC4108RendezvousSessionResource(hs)

    return resources


__all__ = ["build_briij_client_resource_tree"]
