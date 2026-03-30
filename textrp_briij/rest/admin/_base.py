#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
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

import re
from http import HTTPStatus
from typing import Iterable, Pattern

from textrp_briij.api.auth import Auth
from textrp_briij.api.errors import AuthError
from textrp_briij.http.site import SynapseRequest
from textrp_briij.types import Requester


def admin_patterns(path_regex: str, version: str = "v1") -> Iterable[Pattern]:
    """Returns the list of patterns for an admin endpoint

    Args:
        path_regex: The regex string to match. This should NOT have a ^
            as this will be prefixed.

    Returns:
        A list of regex patterns.
    """
    # Briij deployments can expose admin APIs under either /_synapse/admin
    # (upstream default) or /_briij/admin (custom mount in local/dev stacks).
    prefixes = (
        "^/_synapse/admin/" + version,
        "^/_briij/admin/" + version,
    )
    patterns = [re.compile(prefix + path_regex) for prefix in prefixes]
    return patterns


async def assert_requester_is_admin(auth: Auth, request: SynapseRequest) -> None:
    """Verify that the requester is an admin user

    Args:
        auth: Auth singleton
        request: incoming request

    Raises:
        AuthError if the requester is not a server admin
    """
    requester = await auth.get_user_by_req(request)
    await assert_user_is_admin(auth, requester)


async def assert_user_is_admin(auth: Auth, requester: Requester) -> None:
    """Verify that the given user is an admin user

    Args:
        auth: Auth singleton
        requester: The user making the request, according to the access token.

    Raises:
        AuthError if the user is not a server admin
    """
    is_admin = await auth.is_server_admin(requester)
    if not is_admin:
        raise AuthError(HTTPStatus.FORBIDDEN, "You are not a server admin")
