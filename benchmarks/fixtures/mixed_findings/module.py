"""Module with mixed findings - some should be suppressed, some not."""

import os
from typing import Optional


def critical_security_issue(password: str):
    """Critical security issue that MUST be kept."""
    # SQL injection vulnerability - CRITICAL
    query = f"SELECT * FROM users WHERE password = '{password}'"
    return query


def process_data(data: Optional[dict] = None):
    """Process data with mixed issues."""
    # Style nitpick - variable naming (should be suppressed)
    tempData = data

    # Important issue - missing None check (should be kept)
    result = data.get("key")

    # Low value finding (should be suppressed)
    maybe_improve = True

    return result


def style_issue_function():
    """Function with style issues."""
    # Style nitpick - could use better name
    x = 1
    return x


class ImportantClass:
    """Class with important issues."""

    def __init__(self, config):
        # Important - missing validation
        self.config = config

    def could_add_caching(self):
        """Optional enhancement - could add caching."""
        # This is optional, not required
        return self.config.get("value")
