# Python file with issues ruff would catch
import os
import json
from typing import Optional

def process_data(data: dict) -> Optional[str]:
    if not data:
        return None
    return json.dumps(data)
