# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2026 TextRP https://textrp.io
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
"""Compatibility shim for the renamed textrp_briij package."""

from __future__ import annotations

import importlib
import sys
import warnings

warnings.warn(
    "The 'synapse' package has been renamed to 'textrp_briij'. "
    "Please update imports.",
    DeprecationWarning,
    stacklevel=2,
)

_impl = importlib.import_module("textrp_briij")

# Alias the implementation module so submodule imports keep working.
sys.modules[__name__] = _impl
