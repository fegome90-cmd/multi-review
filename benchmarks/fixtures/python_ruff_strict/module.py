"""Module with issues that ruff would catch."""

import os  # unused import - ruff F401
import sys  # unused import - ruff F401
from typing import List, Optional, Dict  # multiple issues possible

def process_items(items):
    """Process items - missing type hints."""
    results = []
    for item in items:
        if item != None:  # comparison to None - ruff E711
            results.append(item)
    return results

def calculate_total(numbers):
    """Calculate total."""
    total = 0
    for i in range(len(numbers)):  # use enumerate - ruff not always catching
        total = total + numbers[i]
    return total

# Line too long - ruff E501 (if over configured limit)
LONG_VARIABLE_NAME_THAT_MIGHT_EXCEED_LINE_LENGTH_LIMIT_IF_THE_PROJECT_HAS_STRICT_LINE_LENGTH_RULES = "value"

class DataProcessor:
    """Data processor class."""

    def __init__(self, config):
        self.config = config

    def process(self, data):
        # bare except - ruff E722
        try:
            return data.process()
        except:
            return None
