"""Module with issues that existing tools already catch.

This file contains issues that ruff or mypy would flag,
making agent findings redundant.
"""

# ruff: F401 - unused import
import os
import sys
from typing import List, Optional


# mypy would catch type issues
def typed_function(items: List[str]) -> int:
    """Function with type hints - mypy validates."""
    # mypy would catch: List has no attribute 'length'
    return items.length  # type: ignore


# ruff would catch various issues
def problematic_function(data: dict) -> Optional[str]:
    """Function with issues ruff catches."""
    # ruff E711: comparison to None
    if data == None:
        return None

    # ruff E501: potentially long line depending on config
    result = data.get("very_long_key_name_that_might_exceed_line_limit_if_the_project_has_strict_rules")
    return result


class TypedClass:
    """Class with type annotations - mypy validates."""

    def __init__(self, name: str) -> None:
        self.name = name

    def get_name(self) -> str:
        """Get the name."""
        return self.name
