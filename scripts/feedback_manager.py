#!/usr/bin/env python3
"""
Feedback manager for multi-review learning system.

This module provides feedback collection and aggregation for learning
from user corrections to reduce false positives over time.

Dependencies:
    - Python 3.10+ stdlib only
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, FrozenSet

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

FEEDBACK_DIR = Path(__file__).parent.parent / "feedback"
AGGREGATE_DIR = FEEDBACK_DIR / "aggregate"
CALIBRATION_FILE = AGGREGATE_DIR / "agent_calibration.json"

# Pattern learning threshold (auto-suppress after this many similar FPs)
FP_THRESHOLD = 3


# =============================================================================
# FEEDBACK TYPE ENUM
# =============================================================================


class FeedbackType(Enum):
    """Types of feedback for a finding.

    Attributes:
        REAL_ISSUE: The finding is a real, actionable issue.
        FALSE_POSITIVE: The finding is incorrect, not an issue.
        ALREADY_FIXED: Issue was already addressed elsewhere.
        NOT_ACTIONABLE: Finding is correct but not worth addressing.
    """

    REAL_ISSUE = "real_issue"
    FALSE_POSITIVE = "false_positive"
    ALREADY_FIXED = "already_fixed"
    NOT_ACTIONABLE = "not_actionable"


# =============================================================================
# FEEDBACK ENTRY DATACLASS
# =============================================================================


@dataclass(frozen=True)
class FeedbackEntry:
    """A single feedback entry for a finding.

    Attributes:
        feedback_id: Unique identifier for this feedback.
        timestamp: ISO timestamp of when feedback was recorded.
        finding_id: ID of the finding being rated.
        file: File path of the finding.
        line: Line number of the finding.
        category: Category of the finding.
        description: Original finding description.
        source_agent: Agent that produced the finding.
        feedback_type: Type of feedback given.
        reason: Optional reason for the feedback.
        severity: Finding severity level.
        confidence: Finding confidence score.
    """

    feedback_id: str
    timestamp: str
    finding_id: str
    file: str
    line: int
    category: str
    description: str
    source_agent: str
    feedback_type: FeedbackType
    reason: Optional[str] = None
    severity: str = "Low"
    confidence: int = 50

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "feedback_id": self.feedback_id,
            "timestamp": self.timestamp,
            "finding_id": self.finding_id,
            "file": self.file,
            "line": self.line,
            "category": self.category,
            "description": self.description,
            "source_agent": self.source_agent,
            "feedback_type": self.feedback_type.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackEntry":
        """Create from dictionary."""
        return cls(
            feedback_id=data["feedback_id"],
            timestamp=data["timestamp"],
            finding_id=data["finding_id"],
            file=data["file"],
            line=data["line"],
            category=data["category"],
            description=data["description"],
            source_agent=data["source_agent"],
            feedback_type=FeedbackType(data["feedback_type"]),
            reason=data.get("reason"),
        )


# =============================================================================
# AGENT CALIBRATION DATACLASS
# =============================================================================


@dataclass
class AgentCalibration:
    """Calibration data for a single agent.

    Tracks feedback statistics and learned patterns for confidence adjustment.

    Attributes:
        agent_name: Name of the agent.
        total_findings: Total findings reviewed.
        real_issues: Count of confirmed real issues.
        false_positives: Count of false positives.
        already_fixed: Count of already-fixed findings.
        not_actionable: Count of not-actionable findings.
        pattern_learnings: List of learned patterns to suppress.
        confidence_adjustment: Overall confidence adjustment factor.
    """

    agent_name: str
    total_findings: int = 0
    real_issues: int = 0
    false_positives: int = 0
    already_fixed: int = 0
    not_actionable: int = 0
    pattern_learnings: List[Dict[str, Any]] = field(default_factory=list)
    confidence_adjustment: float = 1.0

    @property
    def accuracy(self) -> float:
        """Calculate accuracy rate (real issues / total)."""
        if self.total_findings == 0:
            return 0.0
        return self.real_issues / self.total_findings

    @property
    def fp_rate(self) -> float:
        """Calculate false positive rate."""
        if self.total_findings == 0:
            return 0.0
        return self.false_positives / self.total_findings

    def get_confidence_adjustment(self, category: str = "general") -> float:
        """Get confidence adjustment for a specific category.

        Args:
            category: Finding category to get adjustment for.

        Returns:
            Confidence multiplier (0.0-1.0).
        """
        # Base adjustment from overall performance
        base = self.confidence_adjustment

        # Check for category-specific patterns
        for pattern in self.pattern_learnings:
            if pattern.get("category") == category:
                if pattern.get("action") == "suppress":
                    return 0.0  # Suppress completely
                if "adjustment" in pattern:
                    base *= pattern["adjustment"]

        return base

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCalibration":
        """Create from dictionary."""
        return cls(
            agent_name=data["agent_name"],
            total_findings=data.get("total_findings", 0),
            real_issues=data.get("real_issues", 0),
            false_positives=data.get("false_positives", 0),
            already_fixed=data.get("already_fixed", 0),
            not_actionable=data.get("not_actionable", 0),
            pattern_learnings=data.get("pattern_learnings", []),
            confidence_adjustment=data.get("confidence_adjustment", 1.0),
        )


# =============================================================================
# FEEDBACK MANAGER CLASS
# =============================================================================


class FeedbackManager:
    """Manager for feedback collection and calibration.

    This class handles:
    - Recording feedback for findings
    - Aggregating feedback into calibration data
    - Learning patterns from repeated false positives
    - Loading/saving calibration for reuse

    Example:
        >>> manager = FeedbackManager()
        >>> manager.record_feedback(finding, FeedbackType.FALSE_POSITIVE, "Already handled")
        >>> calibration = manager.load_calibration()
    """

    def __init__(self, feedback_dir: Optional[Path] = None):
        """Initialize the feedback manager.

        Args:
            feedback_dir: Directory for feedback storage (defaults to plugin feedback/).
        """
        self.feedback_dir = feedback_dir or FEEDBACK_DIR
        self.aggregate_dir = self.feedback_dir / "aggregate"
        self.calibration_file = self.aggregate_dir / "agent_calibration.json"

        # Ensure directories exist
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.aggregate_dir.mkdir(parents=True, exist_ok=True)

        # In-memory calibration cache
        self._calibration_cache: Optional[Dict[str, Any]] = None

    def _generate_feedback_id(self, finding_id: str) -> str:
        """Generate unique feedback ID.

        Args:
            finding_id: ID of the finding.

        Returns:
            Unique feedback ID.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        hash_input = f"{finding_id}:{timestamp}"
        short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:6]
        return f"fb-{timestamp}-{short_hash}"

    def record_feedback(
        self,
        finding_id: str,
        file: str,
        line: int,
        category: str,
        description: str,
        source_agent: str,
        feedback_type: FeedbackType,
        reason: Optional[str] = None,
        severity: str = "Low",
        confidence: int = 50,
    ) -> FeedbackEntry:
        """Record feedback for a finding.

        Args:
            finding_id: ID of the finding.
            file: File path of the finding.
            line: Line number of the finding.
            category: Category of the finding.
            description: Original finding description.
            source_agent: Agent that produced the finding.
            feedback_type: Type of feedback given.
            reason: Optional reason for the feedback.
            severity: Finding severity.
            confidence: Finding confidence.

        Returns:
            The created FeedbackEntry.
        """
        entry = FeedbackEntry(
            feedback_id=self._generate_feedback_id(finding_id),
            timestamp=datetime.now().isoformat(),
            finding_id=finding_id,
            file=file,
            line=line,
            category=category,
            description=description,
            source_agent=source_agent,
            feedback_type=feedback_type,
            reason=reason,
            severity=severity,
            confidence=confidence,
        )

        # Save individual feedback entry
        self._save_feedback_entry(entry)

        # Update aggregate calibration
        self._update_aggregate_calibration(entry, severity, confidence)

        # Invalidate cache
        self._calibration_cache = None

        logger.info(
            f"Recorded feedback: {feedback_type.value} for {finding_id} "
            f"from {source_agent}"
        )

        return entry

    def _save_feedback_entry(self, entry: FeedbackEntry) -> None:
        """Save a feedback entry to disk.

        Args:
            entry: The feedback entry to save.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"feedback_{timestamp}.json"
        filepath = self.feedback_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, indent=2)
            logger.debug(f"Saved feedback entry to {filepath}")
        except OSError as e:
            logger.error(f"Failed to save feedback entry: {e}")

    def _update_aggregate_calibration(
        self,
        entry: FeedbackEntry,
        severity: str,
        confidence: int,
    ) -> None:
        """Update aggregate calibration with new feedback.

        Args:
            entry: The feedback entry.
            severity: Finding severity.
            confidence: Finding confidence.
        """
        calibration = self._load_calibration_internal()

        # Get or create agent calibration
        agent_calibrations = calibration.get("agent_calibrations", {})

        if entry.source_agent not in agent_calibrations:
            agent_calibrations[entry.source_agent] = AgentCalibration(
                agent_name=entry.source_agent
            ).to_dict()

        agent_cal = agent_calibrations[entry.source_agent]

        # Update counts
        agent_cal["total_findings"] = agent_cal.get("total_findings", 0) + 1

        if entry.feedback_type == FeedbackType.REAL_ISSUE:
            agent_cal["real_issues"] = agent_cal.get("real_issues", 0) + 1
        elif entry.feedback_type == FeedbackType.FALSE_POSITIVE:
            agent_cal["false_positives"] = agent_cal.get("false_positives", 0) + 1
            # Check for pattern learning
            self._check_pattern_learning(agent_cal, entry)
        elif entry.feedback_type == FeedbackType.ALREADY_FIXED:
            agent_cal["already_fixed"] = agent_cal.get("already_fixed", 0) + 1
        elif entry.feedback_type == FeedbackType.NOT_ACTIONABLE:
            agent_cal["not_actionable"] = agent_cal.get("not_actionable", 0) + 1

        # Recalculate confidence adjustment
        total = agent_cal["total_findings"]
        real = agent_cal["real_issues"]
        fp = agent_cal["false_positives"]
        # Adjustment: boost if accurate, reduce if many FPs
        agent_cal["confidence_adjustment"] = max(
            0.5, min(1.0, (real + 0.5) / (total - fp * 0.5))
        )

        agent_calibrations[entry.source_agent] = agent_cal
        calibration["agent_calibrations"] = agent_calibrations
        calibration["last_updated"] = datetime.now().isoformat()

        self._save_calibration(calibration)

    def _check_pattern_learning(
        self,
        agent_cal: Dict[str, Any],
        entry: FeedbackEntry,
    ) -> None:
        """Check if we can learn a pattern from repeated false positives.

        Auto-creates suppression rules after FP_THRESHOLD similar FPs.

        Args:
            agent_cal: Agent calibration dict to update.
            entry: The feedback entry.
        """
        # Extract pattern from description
        pattern = self._extract_pattern(entry.description, entry.category)

        if not pattern:
            return

        patterns = agent_cal.get("pattern_learnings", [])

        # Find existing pattern or create new
        existing = None
        for p in patterns:
            if p.get("pattern") == pattern:
                existing = p
                break

        if existing:
            existing["count"] = existing.get("count", 0) + 1
            if (
                existing["count"] >= FP_THRESHOLD
                and existing.get("action") != "suppress"
            ):
                existing["action"] = "suppress"
                logger.info(
                    f"Learned suppression pattern for {entry.source_agent}: {pattern}"
                )
        else:
            patterns.append(
                {
                    "pattern": pattern,
                    "category": entry.category,
                    "count": 1,
                    "action": "count",  # Just counting for now
                }
            )

        agent_cal["pattern_learnings"] = patterns

    def _extract_pattern(self, description: str, category: str) -> Optional[str]:
        """Extract a learnable pattern from a finding description.

        Args:
            description: Finding description.
            category: Finding category.

        Returns:
            Extracted pattern string, or None if no pattern.
        """
        # Common patterns to extract
        patterns_to_check = [
            # Tool-related patterns
            (r"sql.*orm", "sql_orm_handled"),
            (r"orm.*handles", "orm_handled"),
            (r"ruff.*catches", "tool_ruff_catches"),
            (r"mypy.*catches", "tool_mypy_catches"),
            (r"already.*caught", "tool_already_catches"),
            # Context patterns
            (r"test.*fixture", "test_fixture"),
            (r"test.*mock", "test_mock"),
            (r"internal.*helper", "internal_helper"),
            (r"private.*function", "private_function"),
            # Already handled patterns
            (r"already.*handled", "already_handled"),
            (r"handled.*by", "handled_by_tool"),
        ]

        desc_lower = description.lower()

        for pattern_regex, pattern_name in patterns_to_check:
            if re.search(pattern_regex, desc_lower):
                return pattern_name

        # Category-based pattern
        if category in ["style", "format", "naming"]:
            return f"{category}_nitpick"

        return None

    def _load_calibration_internal(self) -> Dict[str, Any]:
        """Load calibration data from disk (internal use).

        Returns:
            Calibration dictionary.
        """
        if not self.calibration_file.exists():
            return {
                "version": "1.0",
                "agent_calibrations": {},
                "last_updated": datetime.now().isoformat(),
            }

        try:
            with open(self.calibration_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load calibration: {e}")
            return {
                "version": "1.0",
                "agent_calibrations": {},
                "last_updated": datetime.now().isoformat(),
            }

    def load_calibration(self) -> Dict[str, Any]:
        """Load calibration data from disk.

        Uses cache if available.

        Returns:
            Calibration dictionary with agent_calibrations.
        """
        if self._calibration_cache is not None:
            return self._calibration_cache

        calibration = self._load_calibration_internal()
        self._calibration_cache = calibration
        return calibration

    def _save_calibration(self, calibration: Dict[str, Any]) -> None:
        """Save calibration data to disk.

        Args:
            calibration: Calibration dictionary to save.
        """
        try:
            with open(self.calibration_file, "w", encoding="utf-8") as f:
                json.dump(calibration, f, indent=2)
            logger.debug(f"Saved calibration to {self.calibration_file}")
        except OSError as e:
            logger.error(f"Failed to save calibration: {e}")

    def get_agent_calibration(self, agent_name: str) -> AgentCalibration:
        """Get calibration for a specific agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            AgentCalibration object.
        """
        calibration = self.load_calibration()
        agent_cals = calibration.get("agent_calibrations", {})

        if agent_name in agent_cals:
            return AgentCalibration.from_dict(agent_cals[agent_name])

        return AgentCalibration(agent_name=agent_name)

    def get_stats(self) -> Dict[str, Any]:
        """Get overall feedback statistics.

        Returns:
            Dictionary with statistics.
        """
        calibration = self.load_calibration()
        agent_cals = calibration.get("agent_calibrations", {})

        total_findings = 0
        total_real = 0
        total_fp = 0
        total_patterns = 0

        for agent_data in agent_cals.values():
            total_findings += agent_data.get("total_findings", 0)
            total_real += agent_data.get("real_issues", 0)
            total_fp += agent_data.get("false_positives", 0)
            total_patterns += len(agent_data.get("pattern_learnings", []))

        return {
            "total_findings_reviewed": total_findings,
            "total_real_issues": total_real,
            "total_false_positives": total_fp,
            "overall_accuracy": total_real / total_findings
            if total_findings > 0
            else 0,
            "fp_rate": total_fp / total_findings if total_findings > 0 else 0,
            "learned_patterns": total_patterns,
            "agents_with_feedback": len(agent_cals),
            "last_updated": calibration.get("last_updated"),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_feedback_manager() -> FeedbackManager:
    """Get a FeedbackManager instance.

    Returns:
        FeedbackManager instance.
    """
    return FeedbackManager()
