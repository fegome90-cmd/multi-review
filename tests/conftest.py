"""Pytest configuration and fixtures for multi-review plugin tests."""

import sys
from pathlib import Path

# Add scripts directory to Python path for imports
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

import pytest  # noqa: E402


@pytest.fixture
def sample_context():
    """Sample context dictionary for testing."""
    return {
        "has_pr": False,
        "has_tests": True,
        "has_types": False,
        "has_error_handling": False,
        "has_comments": False,
        "change_size": 150,
        "staged_files": ["src/main.py", "tests/test_main.py"],
        "working_files": [],
    }


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file with sample content."""
    test_file = tmp_path / "test.py"
    test_file.write_text("""
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
""")
    return test_file
