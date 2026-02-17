"""Internal helper module with relaxed mypy configuration.

This module contains internal helper functions that don't require
strict type annotations since mypy is not in strict mode.
"""

from typing import Any, Optional


def _internal_helper(data):
    """Internal helper - type annotations optional.

    This is an internal function prefixed with underscore.
    """
    if data is None:
        return None
    return str(data).upper()


def _process_internal(items):
    """Process items internally.

    Another internal helper that doesn't need strict typing.
    """
    results = []
    for item in items:
        results.append(_internal_helper(item))
    return results


class _InternalState:
    """Internal state manager - private class."""

    def __init__(self, config):
        self._config = config
        self._state = {}

    def _get_value(self, key):
        """Get value from internal state."""
        return self._state.get(key)

    def _set_value(self, key, value):
        """Set value in internal state."""
        self._state[key] = value


def create_internal_processor():
    """Factory for internal processor."""
    return _InternalState({"mode": "internal"})
