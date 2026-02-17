#!/usr/bin/env python3
"""
CLI for feedback manager operations.

Usage:
    # Record feedback for a finding
    python3 feedback_manager_cli.py \
        --record \
        --finding-json '{"id":"test-1","file":"x.py","line":1,"category":"security","severity":"Low","confidence":50,"description":"test","source_agent":"test-agent"}' \
        --feedback-type false_positive \
        --reason "Already handled by ORM"

    # Show calibration statistics
    python3 feedback_manager_cli.py --stats

    # Show calibration for a specific agent
    python3 feedback_manager_cli.py --agent "feature-dev:code-reviewer"

Dependencies:
    - Python 3.10+ stdlib only
"""

import argparse
import json
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from feedback_manager import (
    FeedbackManager,
    FeedbackType,
)

from utils import ExitCodes


def record_feedback(
    manager: FeedbackManager,
    finding_json: str,
    feedback_type: str,
    reason: str | None,
) -> int:
    try:
        finding = json.loads(finding_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON for finding: {e}", file=sys.stderr)
        return ExitCodes.INVALID_ARGS

    try:
        fb_type = FeedbackType(feedback_type.lower())
    except ValueError:
        valid_types = [t.value for t in FeedbackType]
        print(
            f"Error: Invalid feedback type. Valid types: {valid_types}", file=sys.stderr
        )
        return ExitCodes.INVALID_ARGS

    entry = manager.record_feedback(
        finding_id=finding.get("id", "unknown"),
        file=finding.get("file", "unknown"),
        line=finding.get("line", 0),
        category=finding.get("category", "general"),
        description=finding.get("description", ""),
        source_agent=finding.get("source_agent", "unknown"),
        feedback_type=fb_type,
        reason=reason,
        severity=finding.get("severity", "Low"),
        confidence=finding.get("confidence", 50),
    )

    print(f"Recorded feedback: {entry.feedback_id}")
    print(f"  Finding: {entry.finding_id}")
    print(f"  Type: {entry.feedback_type.value}")
    print(f"  Agent: {entry.source_agent}")
    if entry.reason:
        print(f"  Reason: {entry.reason}")

    return ExitCodes.SUCCESS


def show_stats(manager: FeedbackManager) -> int:
    """Show calibration statistics.

    Args:
        manager: FeedbackManager instance.

    Returns:
        Exit code (0 for success).
    """
    stats = manager.get_stats()

    print("Feedback Statistics")
    print("=" * 40)
    print(f"Total findings reviewed: {stats['total_findings_reviewed']}")
    print(f"Confirmed real issues: {stats['total_real_issues']}")
    print(f"False positives: {stats['total_false_positives']}")
    print(f"Overall accuracy: {stats['overall_accuracy']:.1%}")
    print(f"False positive rate: {stats['fp_rate']:.1%}")
    print(f"Learned patterns: {stats['learned_patterns']}")
    print(f"Agents with feedback: {stats['agents_with_feedback']}")
    if stats["last_updated"]:
        print(f"Last updated: {stats['last_updated']}")

    return ExitCodes.SUCCESS


def show_agent(manager: FeedbackManager, agent_name: str) -> int:
    """Show calibration for a specific agent.

    Args:
        manager: FeedbackManager instance.
        agent_name: Name of the agent.

    Returns:
        Exit code (0 for success).
    """
    cal = manager.get_agent_calibration(agent_name)

    print(f"Agent Calibration: {agent_name}")
    print("=" * 50)
    print(f"Total findings: {cal.total_findings}")
    print(f"Real issues: {cal.real_issues}")
    print(f"False positives: {cal.false_positives}")
    print(f"Already fixed: {cal.already_fixed}")
    print(f"Not actionable: {cal.not_actionable}")
    print(f"Accuracy: {cal.accuracy:.1%}")
    print(f"FP rate: {cal.fp_rate:.1%}")
    print(f"Confidence adjustment: {cal.confidence_adjustment:.2f}")

    if cal.pattern_learnings:
        print("\nLearned Patterns:")
        for pattern in cal.pattern_learnings:
            action = pattern.get("action", "count")
            count = pattern.get("count", 0)
            pat = pattern.get("pattern", "unknown")
            print(f"  - {pat}: {count} occurrences [{action}]")

    return ExitCodes.SUCCESS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Feedback manager CLI for multi-review learning system"
    )

    # Main actions (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--record", action="store_true", help="Record feedback for a finding"
    )
    action_group.add_argument(
        "--stats", action="store_true", help="Show calibration statistics"
    )
    action_group.add_argument(
        "--agent", metavar="NAME", help="Show calibration for a specific agent"
    )

    # Options for --record
    parser.add_argument(
        "--finding-json", help="JSON string with finding data (for --record)"
    )
    parser.add_argument(
        "--feedback-type",
        choices=["real_issue", "false_positive", "already_fixed", "not_actionable"],
        help="Type of feedback (for --record)",
    )
    parser.add_argument("--reason", help="Reason for the feedback (optional)")

    args = parser.parse_args()
    manager = FeedbackManager()

    if args.record:
        if not args.finding_json:
            print("Error: --finding-json is required for --record", file=sys.stderr)
            return ExitCodes.INVALID_ARGS
        if not args.feedback_type:
            print("Error: --feedback-type is required for --record", file=sys.stderr)
            return ExitCodes.INVALID_ARGS
        return record_feedback(
            manager, args.finding_json, args.feedback_type, args.reason
        )

    elif args.stats:
        return show_stats(manager)

    elif args.agent:
        return show_agent(manager, args.agent)

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
