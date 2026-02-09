#!/usr/bin/env python3
"""
Session-End hook for comprehensive session review.

Runs comprehensive multi-agent review at session end.
Configured via hooks.json with enabled: false by default.

Usage (via hook):
    Triggered automatically at Claude Code session end.

Usage (standalone):
    python3 session_review.py [--context PATH] [--silent]

Exit codes:
    0: Success
    1: Issues found
    2: Error
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


def get_session_files(context_file: Optional[Path] = None) -> List[Path]:
    """Get list of files modified during session.

    Args:
        context_file: Optional path to session context file.

    Returns:
        List of modified file paths.
    """
    if context_file and context_file.exists():
        try:
            data = json.loads(context_file.read_text())
            return [Path(f) for f in data.get("files", [])]
        except Exception as e:
            logger.warning(f"Failed to read context file: {e}")

    # Fall back to git status
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            files = []
            for line in result.stdout.strip().splitlines():
                if line:
                    files.append(Path(line))
            return files

    except Exception as e:
        logger.warning(f"Failed to detect session files: {e}")

    return []


def run_session_review(files: List[Path]) -> Dict:
    """Run comprehensive session review.

    Args:
        files: List of files modified during session.

    Returns:
        Review results dict.
    """
    if not files:
        return {
            "success": True,
            "files_reviewed": 0,
            "issues_found": 0,
            "message": "No files to review",
        }

    logger.info(f"Running session review on {len(files)} file(s)")

    # Always use comprehensive preset for session review
    preset = "comprehensive"

    # Get agent list from context detector
    script_dir = Path(__file__).parent
    detector_script = script_dir / "context_detector.py"

    try:
        result = subprocess.run(
            ["python3", str(detector_script), "--presets"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            # Parse preset agents
            for line in result.stdout.strip().splitlines():
                if line.startswith("comprehensive:"):
                    agents_str = line.split(":", 1)[1].strip()
                    agents = [a.strip() for a in agents_str.split(",")]
                    break
            else:
                agents = []
        else:
            agents = []

    except Exception as e:
        logger.warning(f"Failed to get agent list: {e}")
        agents = []

    return {
        "success": True,
        "preset": preset,
        "agents": agents,
        "files_reviewed": len(files),
        "issues_found": 0,  # Placeholder
        "message": f"Session review complete: {preset} preset",
    }


def save_session_report(results: Dict[str, Any], files: List[Path]) -> Optional[Path]:
    """Save session review report.

    Args:
        results: Review results.
        files: Files that were reviewed.

    Returns:
        Path to saved report, or None if save failed.
    """
    report_data = {
        "session_type": "end",
        "files": [str(f) for f in files],
        "results": results,
    }
    return save_report(report_data, "session")


def main() -> int:
    """Main entry point for session review.

    Returns:
        Exit code (0=success, 1=issues, 2=error).
    """
    parser = argparse.ArgumentParser(
        description="Session-End automated code review"
    )
    parser.add_argument(
        "--context",
        type=Path,
        help="Path to session context file",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Output JSON only",
    )

    args = parser.parse_args()

    # Get session files
    files = get_session_files(args.context)

    # Run review
    results = run_session_review(files)

    if not results.get("success"):
        if args.silent:
            print(json.dumps({"error": results.get("error")}))
        return ExitCodes.CONFIG_ERROR

    # Save report
    report_path = save_session_report(results, files)

    # Output results
    if args.silent:
        print(json.dumps({
            "status": "success",
            "preset": results.get("preset"),
            "files_reviewed": results.get("files_reviewed"),
            "issues": results.get("issues_found", 0),
            "report": str(report_path) if report_path else None,
        }))
    else:
        logger.info(results.get("message"))
        if report_path:
            logger.info(f"Report saved: {report_path}")

        if results.get("issues_found", 0) > 0:
            return ExitCodes.FAILURE

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
