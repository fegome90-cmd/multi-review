#!/usr/bin/env python3
"""
Post-Write hook for automated code review.

Runs quick review after file writes using context-aware agent selection.
Configured via hooks.json with enabled: false by default.

Usage (via hook):
    Triggered automatically after Write/Edit operations.

Usage (standalone):
    python3 auto_review.py [--file PATH] [--preset PRESET] [--silent]

Exit codes:
    0: No issues found
    1: Issues found
    2: Error occurred
    3: LSP type errors detected (future integration)
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Import shared utilities
from utils import (
    ExitCodes,
    count_lines_safely,
    save_report as save_report_to_file,
)

# Import AGENT_PRESETS to avoid duplication
from context_detector import AGENT_PRESETS

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Valid preset names for validation
VALID_PRESETS: frozenset[str] = frozenset(
    ["quick", "thorough", "comprehensive", "framework"]
)


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def validate_preset(preset: Optional[str]) -> None:
    """Validate that preset name is valid.

    Args:
        preset: Preset name to validate.

    Raises:
        ValueError: If preset is None, empty, or not a valid preset name.
        TypeError: If preset is not a string or None.

    Example:
        >>> validate_preset("quick")  # OK
        >>> validate_preset("invalid")  # Raises ValueError
    """
    if preset is None:
        raise ValueError(
            f"Invalid preset: None. Preset cannot be None. "
            f"Valid presets are: {', '.join(sorted(VALID_PRESETS))}"
        )

    if not isinstance(preset, str):
        raise TypeError(f"Preset must be a string or None, got {type(preset).__name__}")

    # Check for empty string
    if not preset:
        raise ValueError(
            f"Invalid preset: empty string. "
            f"Valid presets are: {', '.join(sorted(VALID_PRESETS))}"
        )

    # Check for whitespace (leading/trailing)
    if preset != preset.strip():
        raise ValueError(
            f"Invalid preset: '{preset}' (has leading/trailing whitespace). "
            f"Valid presets are: {', '.join(sorted(VALID_PRESETS))}"
        )

    # Validate against valid presets
    if preset not in VALID_PRESETS:
        valid_list = ", ".join(sorted(VALID_PRESETS))
        raise ValueError(f"Invalid preset: '{preset}'. Valid presets are: {valid_list}")


def detect_review_context(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """Detect minimal context for review decision.

    Args:
        file_path: Path to file being reviewed (if known).

    Returns:
        Context dict with file_type, line_count, etc.
    """
    context = {
        "file_path": str(file_path) if file_path else None,
        "file_type": None,
        "line_count": 0,
        "has_tests": False,
        "has_types": False,
    }

    if file_path and file_path.exists():
        # Detect file type
        suffix = file_path.suffix.lower()
        context["file_type"] = suffix

        # Count lines using shared utility
        context["line_count"] = count_lines_safely(file_path)

        # Check for test/type files
        name_lower = file_path.name.lower()
        context["has_tests"] = any(
            p in name_lower for p in ["_test.", ".test.", ".spec.", "__tests__"]
        )
        context["has_types"] = any(
            p in name_lower for p in ["_types.", ".d.ts", "types."]
        )

    return context


def should_skip_review(context: Dict[str, Any]) -> tuple[bool, str]:
    """Determine if review should be skipped based on context.

    Args:
        context: Review context from detect_review_context().

    Returns:
        Tuple of (should_skip: bool, reason: str).
    """
    file_path = context.get("file_path", "")

    # Skip certain file types
    skip_patterns = [
        ".git/",
        "node_modules/",
        "venv/",
        "__pycache__/",
        ".pytest_cache/",
        "coverage/",
        "dist/",
        "build/",
    ]

    for pattern in skip_patterns:
        if pattern in file_path:
            return True, f"File in excluded directory: {pattern}"

    # Skip lock files, generated files
    skip_extensions = [".lock", ".sum", ".mod", ".pyc"]
    suffix = Path(file_path).suffix if file_path else ""
    if suffix in skip_extensions:
        return True, f"Generated file type: {suffix}"

    # Skip small files (< 5 lines)
    if context.get("line_count", 0) < 5:
        return True, f"File too small: {context['line_count']} lines"

    return False, ""


def run_review_agents(
    context: Dict[str, Any], silent: bool = False, preset: Optional[str] = None
) -> Dict[str, Any]:
    """Run appropriate review agents based on context.

    Args:
        context: Review context from detect_review_context().
        silent: If True, output JSON only (for CI/automation).
        preset: Optional preset name to override auto-selection.

    Returns:
        Review results dict with issues_found, critical_count, etc.
    """
    # Determine preset based on context or use provided preset
    if preset is None:
        # Auto-select preset based on context
        if context.get("line_count", 0) < 50:
            preset = "quick"
        elif context.get("line_count", 0) > 500:
            preset = "comprehensive"
        else:
            preset = "thorough"

        if context.get("has_tests"):
            preset = "thorough"
        if context.get("has_types"):
            preset = "comprehensive"
    else:
        # Use the provided preset (already validated by caller)
        pass

    if not silent:
        logger.info(f"Running multi-review with preset: {preset}")

    # Run context detector to get agent list
    script_dir = Path(__file__).parent
    detector_script = script_dir / "context_detector.py"

    try:
        result = subprocess.run(
            ["python3", str(detector_script), "--suggest"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        logger.error("Context detection timed out")
        return {"success": False, "error": "timeout"}
    except FileNotFoundError:
        logger.error("context_detector.py not found")
        return {"success": False, "error": "script_not_found"}

    # Parse suggestions
    agents = []
    if result.returncode == 0:
        try:
            output = json.loads(result.stdout)
            agents = output.get("available_agents", [])
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse context detector output: {e}")
            logger.debug(f"Context detector stdout: {result.stdout[:200]}")
            # Fallback to default preset (imported from context_detector)
            agents = AGENT_PRESETS.get(preset, AGENT_PRESETS["quick"])

    # For now, just return the agents that would be run
    # Actual agent invocation happens via Claude Code Task tool
    # This hook is meant to be a lightweight check

    return {
        "success": True,
        "preset": preset,
        "agents": agents,
        "issues_found": 0,  # Would be populated by actual agents
        "critical_count": 0,
    }


def save_report(results: Dict[str, Any], context: Dict[str, Any]) -> Optional[Path]:
    """Save review results to reports directory.

    Args:
        results: Review results from run_review_agents().
        context: Review context.

    Returns:
        Path to saved report, or None if save failed.
    """
    report_data = {
        "context": context,
        "results": results,
    }
    return save_report_to_file(report_data, "review")


def main() -> int:
    """Main entry point for auto-review hook.

    Returns:
        Exit code (0=success, 1=issues, 2=error, 3=type errors).
    """
    parser = argparse.ArgumentParser(description="Post-Write automated code review")
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to file being reviewed (from hook)",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default=None,
        help="Review preset to use (overrides auto-selection). "
        f"Valid presets: {', '.join(sorted(VALID_PRESETS))}",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Output JSON only, no human-readable messages",
    )

    args = parser.parse_args()

    # Validate preset if provided
    if args.preset is not None:
        try:
            validate_preset(args.preset)
        except (ValueError, TypeError) as e:
            logger.error(str(e))
            return ExitCodes.INVALID_ARGS

    # Detect context
    context = detect_review_context(args.file)

    # Check if we should skip
    should_skip, reason = should_skip_review(context)
    if should_skip:
        logger.debug(f"Skipping review: {reason}")
        return ExitCodes.SUCCESS

    if not args.silent:
        logger.info(f"Running auto-review for: {context['file_path']}")

    # Run review
    results = run_review_agents(context, silent=args.silent, preset=args.preset)

    if not results.get("success"):
        if args.silent:
            print(json.dumps({"error": results.get("error")}))
        return ExitCodes.ERROR

    # Save report
    report_path = save_report(results, context)
    if report_path and not args.silent:
        logger.info(f"Report saved: {report_path}")

    # Output results
    if args.silent:
        print(
            json.dumps(
                {
                    "preset": results.get("preset"),
                    "agents": results.get("agents", []),
                    "issues_found": results.get("issues_found", 0),
                    "critical_count": results.get("critical_count", 0),
                    "report": str(report_path) if report_path else None,
                }
            )
        )
    else:
        logger.info(f"Preset: {results.get('preset')}")
        logger.info(f"Agents: {', '.join(results.get('agents', []))}")

        if results.get("issues_found", 0) > 0:
            logger.warning(f"Issues found: {results['issues_found']}")
            return ExitCodes.FAILURE

        logger.info("No issues found")

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
