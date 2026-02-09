#!/usr/bin/env python3
"""
Shared utility functions for multi-review plugin.

This module contains common utilities used across all hook scripts
to avoid code duplication and ensure consistent behavior.

Dependencies:
    - Python 3.10+ stdlib only

Common patterns:
    - Exit code constants
    - Report saving
    - Timestamp generation
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExitCodes:
    """Canonical exit codes for all scripts.

    These exit codes provide consistent behavior across all hook scripts
    and standalone tools in the multi-review plugin.

    Attributes:
        SUCCESS: Normal successful execution (0)
        FAILURE: General failure or issues found (1)
        INVALID_ARGS: Invalid command-line arguments (2)
        CONFIG_ERROR: Configuration or setup error (3)
    """
    SUCCESS = 0
    FAILURE = 1
    INVALID_ARGS = 2
    CONFIG_ERROR = 3


# Legacy exit code constants (deprecated, use ExitCodes class instead)
# These are maintained for backward compatibility
EXIT_SUCCESS = 0
EXIT_ISSUES_FOUND = 1
EXIT_ERROR = 2
EXIT_TYPE_ERRORS = 3  # Reserved for LSP integration


def get_reports_dir() -> Path:
    """Get the reports directory, creating it if needed.

    Returns:
        Path to the reports directory.
    """
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    return reports_dir


def generate_timestamp() -> str:
    """Generate a timestamp for report filenames.

    Returns:
        Timestamp string in YYYYMMDD-HHMMSS format.
    """
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def save_report(
    report_data: Dict[str, Any],
    report_type: str,
    prefix: str = "review"
) -> Optional[Path]:
    """Save a report to the reports directory.

    This function consolidates report saving logic used across
    auto_review.py, pre_commit_check.py, and session_review.py.

    Args:
        report_data: Dictionary containing report data.
        report_type: Type of report (for filename, e.g., "commit", "session").
        prefix: Filename prefix (default: "review").

    Returns:
        Path to saved report file, or None if save failed.

    Example:
        >>> data = {"timestamp": "20250209-120000", "results": {}}
        >>> path = save_report(data, "commit")
        >>> print(path)
        ~/reports/commit_20250209-120000.json
    """
    reports_dir = get_reports_dir()
    timestamp = generate_timestamp()
    report_file = reports_dir / f"{report_type}_{timestamp}.json"

    # Add timestamp to report data if not present
    if "timestamp" not in report_data:
        report_data["timestamp"] = timestamp

    try:
        report_file.write_text(json.dumps(report_data, indent=2))
        logger.debug(f"Report saved: {report_file}")
        return report_file
    except OSError as e:
        logger.error(f"Failed to save report to {report_file}: {e}")
        return None


def format_report_summary(
    preset: str,
    agents: List[str],
    issues_found: int = 0,
    critical_count: int = 0
) -> Dict[str, Any]:
    """Format a standard report summary dictionary.

    Args:
        preset: Preset name used for review.
        agents: List of agents that were run.
        issues_found: Total number of issues found.
        critical_count: Number of critical issues.

    Returns:
        Formatted summary dictionary.
    """
    return {
        "preset": preset,
        "agents": agents,
        "issues_found": issues_found,
        "critical_count": critical_count,
    }


def log_review_summary(
    preset: str,
    agents: List[str],
    issues_found: int = 0,
    report_path: Optional[Path] = None
) -> None:
    """Log a standardized review summary.

    Args:
        preset: Preset name used.
        agents: List of agents that were run.
        issues_found: Number of issues found.
        report_path: Path to saved report (optional).
    """
    logger.info(f"Preset: {preset}")
    logger.info(f"Agents: {', '.join(agents)}")

    if issues_found > 0:
        logger.warning(f"Issues found: {issues_found}")
    else:
        logger.info("No issues found")

    if report_path:
        logger.info(f"Report saved: {report_path}")


def validate_file_path(file_path: Optional[Path]) -> bool:
    """Validate that a file path exists and is accessible.

    Args:
        file_path: Path to validate.

    Returns:
        True if file exists and is readable, False otherwise.
    """
    if file_path is None:
        return False

    try:
        return file_path.exists() and file_path.is_file()
    except OSError:
        return False


def count_lines_safely(file_path: Path) -> int:
    """Count lines in a file with comprehensive error handling.

    This replaces the bare except Exception pattern with specific handlers.

    Args:
        file_path: Path to the file.

    Returns:
        Number of lines, or 0 if reading failed.
    """
    try:
        return len(file_path.read_text().splitlines())
    except PermissionError as e:
        logger.warning(f"Cannot read file {file_path}: permission denied: {e}")
        return 0
    except UnicodeDecodeError as e:
        logger.warning(f"Cannot read file {file_path}: encoding error: {e}")
        return 0
    except OSError as e:
        logger.warning(f"Cannot read file {file_path}: I/O error: {e}")
        return 0
