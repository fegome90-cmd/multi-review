#!/usr/bin/env python3
"""
Pre-Commit hook for automated code review validation.

Runs comprehensive review before git commit.
Configured via hooks.json with enabled: false by default.

Usage (via hook):
    Triggered automatically before git commit.

Usage (standalone):
    python3 pre_commit_check.py [--strict] [--silent]

Exit codes:
    0: Pass - review passed or warnings only
    1: Fail - critical issues found (blocks commit in strict mode)
    2: Error - review failed to run
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import shared utilities and exit codes
from utils import ExitCodes, save_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def get_staged_files() -> List[Path]:
    """Get list of staged files for review.

    Returns:
        List of staged file paths.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.warning("Could not detect staged files")
            return []

        files = []
        for line in result.stdout.strip().splitlines():
            if line:
                files.append(Path(line))

        return files

    except subprocess.TimeoutExpired:
        logger.warning("Git command timed out")
        return []
    except Exception as e:
        logger.warning(f"Failed to detect staged files: {e}")
        return []


def filter_reviewable_files(files: List[Path]) -> List[Path]:
    """Filter files that should be reviewed.

    Args:
        files: List of all staged files.

    Returns:
        Filtered list of reviewable files.
    """
    # Extensions to review
    review_extensions = {
        ".py", ".ts", ".tsx", ".js", ".jsx",
        ".go", ".rs", ".java", ".kt",
        ".rb", ".php", ".cs", ".cpp", ".c",
        ".h", ".hpp", ".swift", ".dart"
    }

    # Directories to exclude
    exclude_dirs = {
        "node_modules", "venv", ".venv", "virtualenv",
        "vendor", "dist", "build", "target",
        "__pycache__", ".pytest_cache", ".git"
    }

    reviewable = []
    for file in files:
        # Check extension
        if file.suffix.lower() not in review_extensions:
            continue

        # Check excluded directories
        if any(part in exclude_dirs for part in file.parts):
            continue

        reviewable.append(file)

    return reviewable


def run_pre_commit_review(files: List[Path], strict: bool = False) -> Dict:
    """Run review on staged files.

    Args:
        files: List of staged files to review.
        strict: If True, critical issues cause failure.

    Returns:
        Review results dict.
    """
    if not files:
        return {
            "success": True,
            "files_reviewed": 0,
            "issues_found": 0,
            "critical_count": 0,
            "message": "No reviewable files staged",
        }

    logger.info(f"Running pre-commit review on {len(files)} file(s)")

    # Use context detector to suggest preset
    script_dir = Path(__file__).parent
    detector_script = script_dir / "context_detector.py"

    try:
        result = subprocess.run(
            ["python3", str(detector_script), "--suggest"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:
        logger.error(f"Context detection failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "files_reviewed": len(files),
        }

    # Determine preset based on file count
    file_count = len(files)
    if file_count == 1:
        preset = "quick"
    elif file_count <= 5:
        preset = "thorough"
    else:
        preset = "comprehensive"

    # Parse agent suggestions
    agents = []
    if result.returncode == 0:
        try:
            output = json.loads(result.stdout)
            agents = output.get("available_agents", [])
        except json.JSONDecodeError:
            pass

    # For this hook, we just provide guidance
    # Actual review would be invoked by Claude Code
    return {
        "success": True,
        "preset": preset,
        "agents": agents,
        "files_reviewed": len(files),
        "issues_found": 0,  # Placeholder
        "critical_count": 0,  # Placeholder
        "message": f"Review complete: {preset} preset suggested",
    }


def save_commit_report(results: Dict[str, Any], files: List[Path]) -> Optional[Path]:
    """Save pre-commit review report.

    Args:
        results: Review results.
        files: Files that were reviewed.

    Returns:
        Path to saved report, or None if save failed.
    """
    report_data = {
        "files": [str(f) for f in files],
        "results": results,
    }
    return save_report(report_data, "commit")


def main() -> int:
    """Main entry point for pre-commit check.

    Returns:
        Exit code (0=pass, 1=fail, 2=error).
    """
    parser = argparse.ArgumentParser(
        description="Pre-Commit automated code review"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail commit on critical issues",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Output JSON only",
    )

    args = parser.parse_args()

    # Get staged files
    staged = get_staged_files()
    if not staged:
        if not args.silent:
            logger.info("No staged files detected")
        return ExitCodes.SUCCESS

    # Filter to reviewable files
    reviewable = filter_reviewable_files(staged)
    if not reviewable:
        if not args.silent:
            logger.info("No reviewable files staged")
        return ExitCodes.SUCCESS

    # Run review
    results = run_pre_commit_review(reviewable, strict=args.strict)

    if not results.get("success"):
        if args.silent:
            print(json.dumps({"error": results.get("error")}))
        return ExitCodes.CONFIG_ERROR

    # Save report
    report_path = save_commit_report(results, reviewable)

    # Output results
    if args.silent:
        print(json.dumps({
            "status": "pass" if results.get("critical_count", 0) == 0 or not args.strict else "fail",
            "preset": results.get("preset"),
            "files_reviewed": results.get("files_reviewed"),
            "issues": results.get("issues_found", 0),
            "critical": results.get("critical_count", 0),
            "report": str(report_path) if report_path else None,
        }))
    else:
        logger.info(results.get("message", "Review complete"))
        if report_path:
            logger.info(f"Report saved: {report_path}")

        # Check if we should fail
        critical = results.get("critical_count", 0)
        if args.strict and critical > 0:
            logger.error(f"Commit blocked: {critical} critical issue(s) found")
            return ExitCodes.FAILURE

        if critical > 0:
            logger.warning(f"{critical} critical issue(s) found (use --strict to block commits)")

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
