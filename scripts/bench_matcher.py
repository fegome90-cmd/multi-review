#!/usr/bin/env python3
"""
Benchmark matcher for multi-review false positive evaluation.

This module provides pattern-based matching to classify findings against
expected labels. It supports flexible matching on category, file, severity,
confidence, and description patterns.

Key Design Principles:
- Pattern-based matching (not exact text comparison)
- Support for multiple match criteria per label
- Classification into TP/FP/SUPPRESSED/UNLABELED

Dependencies:
    - Python 3.10+ stdlib only
    - finding_filter.py (for Finding)
"""

import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Pattern


class Classification(Enum):
    """Classification of a finding against expected labels.

    Attributes:
        TP: True Positive - finding is valid and expected
        FP: False Positive - finding is not valid
        SUPPRESSED: Finding was correctly suppressed by filter
        UNLABELED: No matching label found in expected.json
    """
    TP = "TP"
    FP = "FP"
    SUPPRESSED = "SUPPRESSED"
    UNLABELED = "UNLABELED"


@dataclass(frozen=True)
class MatchCriteria:
    """Criteria for matching a finding to a label.

    All criteria are optional - if not specified, they won't be checked.
    Multiple criteria are combined with AND logic.

    Attributes:
        category: Category to match (exact or pattern).
        file: File path to match (glob pattern supported).
        severity: Severity level to match.
        confidence_min: Minimum confidence threshold.
        confidence_max: Maximum confidence threshold.
        description_pattern: Regex or glob pattern for description.
        line_min: Minimum line number.
        line_max: Maximum line number.
    """
    category: Optional[str] = None
    file: Optional[str] = None
    severity: Optional[str] = None
    confidence_min: Optional[int] = None
    confidence_max: Optional[int] = None
    description_pattern: Optional[str] = None
    line_min: Optional[int] = None
    line_max: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate match criteria."""
        if self.confidence_min is not None and not 0 <= self.confidence_min <= 100:
            raise ValueError(f"confidence_min must be 0-100, got {self.confidence_min}")
        if self.confidence_max is not None and not 0 <= self.confidence_max <= 100:
            raise ValueError(f"confidence_max must be 0-100, got {self.confidence_max}")
        if (self.confidence_min is not None and self.confidence_max is not None and
            self.confidence_min > self.confidence_max):
            raise ValueError(f"confidence_min ({self.confidence_min}) > confidence_max ({self.confidence_max})")


@dataclass(frozen=True)
class ExpectedLabel:
    """Expected label for a finding.

    Attributes:
        match: Criteria for matching findings.
        expected: Expected classification (TP, FP, SUPPRESSED).
        reason_code: Expected reason code for suppression.
        note: Optional note explaining the expectation.
    """
    match: MatchCriteria
    expected: Classification
    reason_code: Optional[str] = None
    note: Optional[str] = None


@dataclass
class MatcherConfig:
    """Configuration for the benchmark matcher.

    Attributes:
        line_tolerance: Maximum line number difference for matching.
        case_sensitive_file: Whether file paths are case-sensitive.
        case_sensitive_category: Whether categories are case-sensitive.
        description_pattern_type: 'regex' or 'glob' for description patterns.
    """
    line_tolerance: int = 2
    case_sensitive_file: bool = True
    case_sensitive_category: bool = False
    description_pattern_type: str = "regex"  # or "glob"


# =============================================================================
# PATTERN MATCHING FUNCTIONS
# =============================================================================

def compile_description_pattern(
    pattern: str,
    pattern_type: str = "regex"
) -> Pattern[str]:
    """Compile a description pattern for matching.

    Args:
        pattern: The pattern string (regex or glob).
        pattern_type: 'regex' or 'glob'.

    Returns:
        Compiled regex pattern.
    """
    if pattern_type == "glob":
        # Convert glob to regex
        regex = fnmatch.translate(pattern)
        return re.compile(regex, re.IGNORECASE)
    else:
        # Treat as regex
        return re.compile(pattern, re.IGNORECASE)


def match_category(
    finding_category: str,
    pattern: str,
    case_sensitive: bool = False
) -> bool:
    """Match finding category against pattern.

    Supports exact match and common variations (e.g., error_handling vs error-handling).

    Args:
        finding_category: The finding's category.
        pattern: The pattern to match against.
        case_sensitive: Whether matching is case-sensitive.

    Returns:
        True if category matches.
    """
    if not case_sensitive:
        finding_category = finding_category.lower()
        pattern = pattern.lower()

    # Exact match
    if finding_category == pattern:
        return True

    # Normalize variations: error_handling == error-handling == error handling
    normalized_finding = finding_category.replace("-", "_").replace(" ", "_")
    normalized_pattern = pattern.replace("-", "_").replace(" ", "_")

    return normalized_finding == normalized_pattern


def match_file(
    finding_file: str,
    pattern: str,
    case_sensitive: bool = True
) -> bool:
    """Match finding file against pattern.

    Supports glob patterns (e.g., "src/**/*.py").

    Args:
        finding_file: The finding's file path.
        pattern: The glob pattern to match against.
        case_sensitive: Whether matching is case-sensitive.

    Returns:
        True if file matches.
    """
    if not case_sensitive:
        finding_file = finding_file.lower()
        pattern = pattern.lower()

    # Exact match
    if finding_file == pattern:
        return True

    # Glob match
    return fnmatch.fnmatch(finding_file, pattern)


def match_description(
    finding_description: str,
    pattern: str,
    pattern_type: str = "regex"
) -> bool:
    """Match finding description against pattern.

    Args:
        finding_description: The finding's description.
        pattern: The pattern (regex or glob).
        pattern_type: 'regex' or 'glob'.

    Returns:
        True if description matches.
    """
    try:
        compiled = compile_description_pattern(pattern, pattern_type)
        return bool(compiled.search(finding_description))
    except re.error:
        # If regex fails, try simple substring match
        return pattern.lower() in finding_description.lower()


def match_confidence(
    finding_confidence: int,
    min_confidence: Optional[int],
    max_confidence: Optional[int]
) -> bool:
    """Check if finding confidence is within range.

    Args:
        finding_confidence: The finding's confidence.
        min_confidence: Minimum confidence (None = no minimum).
        max_confidence: Maximum confidence (None = no maximum).

    Returns:
        True if confidence is within range.
    """
    if min_confidence is not None and finding_confidence < min_confidence:
        return False
    if max_confidence is not None and finding_confidence > max_confidence:
        return False
    return True


# =============================================================================
# MAIN MATCHER FUNCTIONS
# =============================================================================

def match_finding_to_label(
    finding: "Finding",
    label: ExpectedLabel,
    config: Optional[MatcherConfig] = None
) -> bool:
    """Check if a finding matches a label's criteria.

    All specified criteria must match (AND logic).

    Args:
        finding: The finding to match.
        label: The expected label with match criteria.
        config: Matcher configuration (uses defaults if None).

    Returns:
        True if finding matches all specified criteria.

    Example:
        >>> from finding_filter import Finding
        >>> finding = Finding(
        ...     id="test", file="script.sh", line=1,
        ...     category="error_handling", severity="Low", confidence=50,
        ...     description="Missing error check"
        ... )
        >>> label = ExpectedLabel(
        ...     match=MatchCriteria(category="error_handling", file="script.sh"),
        ...     expected=Classification.SUPPRESSED,
        ...     reason_code="L2_SHELL_STRICT_MODE"
        ... )
        >>> match_finding_to_label(finding, label)
        True
    """
    config = config or MatcherConfig()
    criteria = label.match

    # Check category
    if criteria.category is not None:
        if not match_category(
            finding.category,
            criteria.category,
            config.case_sensitive_category
        ):
            return False

    # Check file
    if criteria.file is not None:
        if not match_file(
            finding.file,
            criteria.file,
            config.case_sensitive_file
        ):
            return False

    # Check severity
    if criteria.severity is not None:
        if finding.severity.lower() != criteria.severity.lower():
            return False

    # Check confidence range
    if not match_confidence(
        finding.confidence,
        criteria.confidence_min,
        criteria.confidence_max
    ):
        return False

    # Check description pattern
    if criteria.description_pattern is not None:
        if not match_description(
            finding.description,
            criteria.description_pattern,
            config.description_pattern_type
        ):
            return False

    # Check line range
    if criteria.line_min is not None and finding.line < criteria.line_min:
        return False
    if criteria.line_max is not None and finding.line > criteria.line_max:
        return False

    return True


def classify_finding(
    finding: "Finding",
    labels: List[ExpectedLabel],
    config: Optional[MatcherConfig] = None,
    is_suppressed: bool = False,
    actual_reason_code: Optional[str] = None
) -> Classification:
    """Classify a finding based on expected labels.

    Args:
        finding: The finding to classify.
        labels: List of expected labels to match against.
        config: Matcher configuration.
        is_suppressed: Whether the finding was actually suppressed by filter.
        actual_reason_code: The actual reason code from filtering.

    Returns:
        Classification (TP, FP, SUPPRESSED, or UNLABELED).

    Example:
        >>> labels = [
        ...     ExpectedLabel(
        ...         match=MatchCriteria(category="error_handling"),
        ...         expected=Classification.SUPPRESSED,
        ...         reason_code="L2_SHELL_STRICT_MODE"
        ...     )
        ... ]
        >>> classify_finding(finding, labels, is_suppressed=True)
        Classification.SUPPRESSED
    """
    config = config or MatcherConfig()

    # Find first matching label
    for label in labels:
        if match_finding_to_label(finding, label, config):
            expected = label.expected

            # If we expect SUPPRESSED and it was suppressed, that's correct
            if expected == Classification.SUPPRESSED:
                if is_suppressed:
                    return Classification.SUPPRESSED
                # Expected suppression but not suppressed = FP
                return Classification.FP

            # If we expect TP and it wasn't suppressed
            if expected == Classification.TP:
                if not is_suppressed:
                    return Classification.TP
                # Expected TP but was suppressed = FP (over-suppression)
                return Classification.FP

            # If we expect FP and it wasn't suppressed
            if expected == Classification.FP:
                return Classification.FP

            return expected

    # No matching label found
    return Classification.UNLABELED


def classify_finding_with_details(
    finding: "Finding",
    labels: List[ExpectedLabel],
    config: Optional[MatcherConfig] = None,
    is_suppressed: bool = False,
    actual_reason_code: Optional[str] = None
) -> Dict[str, Any]:
    """Classify a finding and return detailed results.

    Args:
        finding: The finding to classify.
        labels: List of expected labels.
        config: Matcher configuration.
        is_suppressed: Whether the finding was actually suppressed.
        actual_reason_code: The actual reason code from filtering.

    Returns:
        Dictionary with classification details including:
        - classification: The Classification enum value
        - matched_label: The matching ExpectedLabel (if any)
        - expected_reason_code: Expected reason code from label
        - actual_reason_code: Actual reason code from filter
        - reason_match: Whether reason codes match
    """
    config = config or MatcherConfig()

    result = {
        "finding_id": finding.id,
        "file": finding.file,
        "category": finding.category,
        "classification": Classification.UNLABELED,
        "matched_label": None,
        "expected_reason_code": None,
        "actual_reason_code": actual_reason_code,
        "reason_match": False,
    }

    for label in labels:
        if match_finding_to_label(finding, label, config):
            result["matched_label"] = label
            result["expected_reason_code"] = label.reason_code

            expected = label.expected

            if expected == Classification.SUPPRESSED:
                if is_suppressed:
                    result["classification"] = Classification.SUPPRESSED
                    # Check if reason codes match
                    if label.reason_code and actual_reason_code:
                        result["reason_match"] = (
                            label.reason_code.lower() == actual_reason_code.lower()
                        )
                else:
                    result["classification"] = Classification.FP
            elif expected == Classification.TP:
                if not is_suppressed:
                    result["classification"] = Classification.TP
                else:
                    result["classification"] = Classification.FP
            else:
                result["classification"] = expected

            break

    return result


# =============================================================================
# LABEL LOADING FROM JSON
# =============================================================================

def load_expected_labels_from_dict(data: Dict[str, Any]) -> List[ExpectedLabel]:
    """Load expected labels from a dictionary (parsed JSON).

    Args:
        data: Dictionary with 'labels' key containing label definitions.

    Returns:
        List of ExpectedLabel objects.

    Example:
        >>> data = {
        ...     "labels": [
        ...         {
        ...             "match": {"category": "error_handling", "file": "script.sh"},
        ...             "expected": "SUPPRESSED",
        ...             "reason_code": "L2_SHELL_STRICT_MODE"
        ...         }
        ...     ]
        ... }
        >>> labels = load_expected_labels_from_dict(data)
        >>> len(labels)
        1
    """
    labels = []

    for label_data in data.get("labels", []):
        match_data = label_data.get("match", {})

        criteria = MatchCriteria(
            category=match_data.get("category"),
            file=match_data.get("file"),
            severity=match_data.get("severity"),
            confidence_min=match_data.get("confidence_min"),
            confidence_max=match_data.get("confidence_max"),
            description_pattern=match_data.get("description_pattern"),
            line_min=match_data.get("line_min"),
            line_max=match_data.get("line_max"),
        )

        expected_str = label_data.get("expected", "UNLABELED").upper()
        try:
            expected = Classification[expected_str]
        except KeyError:
            expected = Classification.UNLABELED

        label = ExpectedLabel(
            match=criteria,
            expected=expected,
            reason_code=label_data.get("reason_code"),
            note=label_data.get("note"),
        )
        labels.append(label)

    return labels


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_classification_stats(
    classifications: List[Classification]
) -> Dict[str, int]:
    """Get statistics from a list of classifications.

    Args:
        classifications: List of Classification values.

    Returns:
        Dictionary with counts for each classification type.
    """
    stats = {
        "TP": 0,
        "FP": 0,
        "SUPPRESSED": 0,
        "UNLABELED": 0,
        "total": len(classifications),
    }

    for c in classifications:
        stats[c.value] += 1

    return stats


def calculate_metrics(
    true_positives: int,
    false_positives: int,
    total_expected: int
) -> Dict[str, float]:
    """Calculate precision, recall, and F1 score.

    Args:
        true_positives: Number of true positives.
        false_positives: Number of false positives.
        total_expected: Total number of expected positive findings.

    Returns:
        Dictionary with precision, recall, F1, and accuracy.
    """
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / total_expected if total_expected > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


if __name__ == "__main__":
    # Demo/test of the matcher
    import json
    import sys

    # Add scripts to path for Finding import
    sys.path.insert(0, str(Path(__file__).parent))

    from finding_filter import Finding

    # Create a sample finding
    finding = Finding(
        id="test-001",
        file="script.sh",
        line=10,
        category="error_handling",
        severity="Low",
        confidence=50,
        description="Missing error handling for command",
    )

    # Create a label
    label = ExpectedLabel(
        match=MatchCriteria(category="error_handling", file="script.sh"),
        expected=Classification.SUPPRESSED,
        reason_code="L2_SHELL_STRICT_MODE",
    )

    # Test matching
    print(f"Finding: {finding.file}:{finding.line} - {finding.category}")
    print(f"Label match: {match_finding_to_label(finding, label)}")

    # Test classification
    result = classify_finding_with_details(
        finding, [label],
        is_suppressed=True,
        actual_reason_code="L2_SHELL_STRICT_MODE"
    )
    print(f"Classification: {result['classification'].value}")
    print(f"Reason match: {result['reason_match']}")
