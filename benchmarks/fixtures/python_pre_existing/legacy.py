"""Legacy module with pre-existing code issues.

This file represents code that existed before the current PR.
Findings about pre-existing code should have reduced confidence.
"""


def legacy_function_no_types(data):
    """Legacy function from 2020 - no type hints.

    This code was written before type hints were standard.
    """
    result = []
    for item in data:
        if item is not None:
            result.append(item.upper())
    return result


class LegacyClass:
    """Legacy class from old codebase.

    This class has been in the codebase for years.
    """

    def __init__(self, config):
        # Pre-existing: missing validation (been there since 2019)
        self.config = config

    def process(self):
        """Process method."""
        # Pre-existing issue: no error handling
        return self.config["key"]


# Global variable from original implementation
LEGACY_CONFIG = {"mode": "old"}
