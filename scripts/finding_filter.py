#!/usr/bin/env python3
"""
Finding filter for multi-review false positive elimination.

This module implements Layer 2 of the 3-Layer Defense system:
- Mechanical filtering using typed predicates (not string DSLs)
- Context-aware suppression of false positives
- Evidence-based confidence adjustment

Key Design Principle: Use typed predicate functions rather than string DSLs.
This makes the filter easier to test, harder to break, and more maintainable.

Dependencies:
    - Python 3.10+ stdlib only
    - project_context.py (for ProjectContext)
"""

import dataclasses
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# FILTER ACTION ENUM
# =============================================================================

class FilterAction(Enum):
    """Actions that can be taken on a finding.

    Attributes:
        SUPPRESS: Remove from output entirely (log reason)
        SET_CONFIDENCE: Set confidence to a specific value
    """
    SUPPRESS = "suppress"
    SET_CONFIDENCE = "set_confidence"


# =============================================================================
# SUPPRESSION REASON CODES (Namespaced by Layer)
# =============================================================================

class SuppressionReasonCode(Enum):
    """Canonical reason codes with layer namespace.

    L2_* codes are for Layer 2 (Mechanical Filtering).
    L3_* codes are for Layer 3 (Evidence-Based Validation).

    Attributes:
        L2_SHELL_STRICT_MODE: Shell script has `set -euo pipefail`.
        L2_STYLE_NITPICK: Non-actionable style issue.
        L2_INTERNAL_HELPER: Internal helper function, mypy not strict.
        L2_MYPY_NOT_STRICT: Mypy configured as relaxed.
        L2_LOW_VALUE: Low confidence AND low severity.
        L2_TOOL_ALREADY_CATCHES: Existing tool already catches this.
        L2_OPTIONAL_ENHANCEMENT: Optional enhancement suggestion.
        L2_PRE_EXISTING_CODE: Pre-existing code (not changed in this PR).
        L2_LEARNED_PATTERN: Learned from feedback patterns.

        L3_NO_EVIDENCE_MATCH: No tool evidence supports finding.
        L3_VALIDATION_CONTRADICTED: Tool output contradicts finding.
        L3_TOOL_TIMEOUT: Tool timed out during validation.
        L3_TOOL_MISSING: Tool not installed or available.
    """
    # Layer 2: Mechanical Filtering
    L2_SHELL_STRICT_MODE = "L2_shell_strict_mode"
    L2_STYLE_NITPICK = "L2_style_nitpick"
    L2_INTERNAL_HELPER = "L2_internal_helper"
    L2_MYPY_NOT_STRICT = "L2_mypy_not_strict"
    L2_LOW_VALUE = "L2_low_value"
    L2_TOOL_ALREADY_CATCHES = "L2_tool_already_catches"
    L2_OPTIONAL_ENHANCEMENT = "L2_optional_enhancement"
    L2_PRE_EXISTING_CODE = "L2_pre_existing_code"
    L2_LEARNED_PATTERN = "L2_learned_pattern"

    # Layer 3: Evidence-Based Validation
    L3_NO_EVIDENCE_MATCH = "L3_no_evidence_match"
    L3_VALIDATION_CONTRADICTED = "L3_validation_contradicted"
    L3_TOOL_TIMEOUT = "L3_tool_timeout"
    L3_TOOL_MISSING = "L3_tool_missing"


# =============================================================================
# FINDING DATACLASS
# =============================================================================

@dataclass(frozen=True)
class Finding:
    """A code review finding from an agent.

    Attributes:
        id: Unique identifier for this finding.
        file: File path (relative to repo root).
        line: Line number (1-indexed).
        category: Category of issue (e.g., 'error_handling', 'type_annotation').
        severity: Severity level ('Critical', 'Important', 'Low').
        confidence: Confidence score (0-100).
        description: Human-readable description of the issue.
        suggested_fix: Optional suggested fix.
        evidence_refs: Links to tool outputs or other evidence.
        source_agent: Name of the agent that found this issue.
    """
    id: str
    file: str
    line: int
    category: str
    severity: str
    confidence: int
    description: str
    suggested_fix: Optional[str] = None
    evidence_refs: FrozenSet[str] = frozenset()
    source_agent: str = "unknown"

    def __post_init__(self) -> None:
        """Validate finding data."""
        if not 0 <= self.confidence <= 100:
            raise ValueError(f"Confidence must be 0-100, got {self.confidence}")
        if not self.file:
            raise ValueError("File path cannot be empty")
        if self.line < 0:
            raise ValueError(f"Line number must be >= 0, got {self.line}")


# =============================================================================
# TYPED PREDICATES
# =============================================================================

# Type alias for predicate functions
# Predicate takes (finding, context) and returns bool
PredicateFn = Callable[[Finding, "ProjectContext"], bool]


def is_shell_strict_mode(finding: Finding, context: "ProjectContext") -> bool:
    """Check if finding is in a shell file with strict mode enabled.

    Shell scripts with `set -euo pipefail` already handle errors properly,
    so error-handling findings in these files are false positives.

    Args:
        finding: The finding to check.
        context: Project context with shell configuration.

    Returns:
        True if finding is in a strict-mode shell file about error handling.
    """
    # Check if it's a shell file
    shell_extensions = {'.sh', '.bash', '.zsh'}
    file_path = Path(finding.file)

    if file_path.suffix not in shell_extensions:
        return False

    # Check if this file has strict mode
    if file_path not in context.shell_config.strict_mode_files:
        # Check with string comparison as well
        if finding.file not in [str(p) for p in context.shell_config.strict_mode_files]:
            return False

    # Check if the finding is about error handling
    error_categories = {'error_handling', 'error-handling', 'error handling'}
    if finding.category.lower() in error_categories:
        return True

    # Also check description for error-related terms
    error_terms = {'error handling', 'error check', 'exit code', 'error condition'}
    desc_lower = finding.description.lower()
    if any(term in desc_lower for term in error_terms):
        return True

    return False


def is_style_nitpick(finding: Finding, context: "ProjectContext") -> bool:
    """Check if finding is a style nitpick that should be suppressed.

    Style nitpicks are low-severity issues about formatting, naming, etc.
    that don't represent actual bugs or security issues.

    Args:
        finding: The finding to check.
        context: Project context (unused but required for signature).

    Returns:
        True if finding is a style nitpick.
    """
    # Must be low severity
    if finding.severity.lower() != 'low':
        return False

    # Check for nitpick-related terms in description
    nitpick_terms = {
        'naming', 'style', 'format', 'formatting',
        'redundant', 'unused', 'unnecessary',
        'prefer', 'consider', 'could be',
        'whitespace', 'indentation', 'line length',
    }

    desc_lower = finding.description.lower()
    return any(term in desc_lower for term in nitpick_terms)


def is_optional_enhancement(finding: Finding, context: "ProjectContext") -> bool:
    """Check if finding is an optional enhancement suggestion.

    These are valid suggestions but not actionable issues.

    Args:
        finding: The finding to check.
        context: Project context (unused but required for signature).

    Returns:
        True if finding is an optional enhancement.
    """
    enhancement_terms = {
        'could', 'might', 'consider', 'optional',
        'enhancement', 'improvement', 'suggestion',
        'could use', 'could add', 'might want',
        'for consistency', 'for clarity',
    }

    desc_lower = finding.description.lower()
    return any(term in desc_lower for term in enhancement_terms)


def is_internal_helper(finding: Finding, context: "ProjectContext") -> bool:
    """Check if finding is about an internal helper function.

    Internal helpers (prefixed with _) don't need strict type annotations
    if the project isn't using mypy strict mode.

    Args:
        finding: The finding to check.
        context: Project context with Python configuration.

    Returns:
        True if finding is about internal helper and mypy is not strict.
    """
    # Only applies to type annotation findings
    type_categories = {'type_annotation', 'type-annotation', 'typing'}
    if finding.category.lower() not in type_categories:
        return False

    # Check if mypy is strict - if so, we shouldn't suppress
    if context.python_config.mypy_strict.value:
        return False

    # Check if description mentions internal/private functions
    internal_terms = {'internal', 'private', 'helper', '_'}
    desc_lower = finding.description.lower()

    # Check if it's about a function starting with underscore
    if any(term in desc_lower for term in internal_terms):
        return True

    # Check if the file contains underscore-prefixed names in the description
    if '_' in finding.description:
        # Likely about an internal function
        return True

    return False


def is_pre_existing_issue(finding: Finding, context: "ProjectContext") -> bool:
    """Check if finding is about pre-existing code (not changed in this PR).

    Uses git blame to identify code written by others.
    Note: This predicate requires git_metadata with pre_existing_issue_authors.

    Args:
        finding: The finding to check.
        context: Project context with git metadata.

    Returns:
        True if finding is in pre-existing code (confidence should be reduced).
    """
    # If we have git metadata with pre-existing authors
    if not context.git_metadata.pre_existing_issue_authors:
        return False

    # Check if the file is in the changed files
    if finding.file not in context.git_metadata.changed_files:
        return True  # File not changed, so it's pre-existing

    return False


def is_low_value_finding(finding: Finding, context: "ProjectContext") -> bool:
    """Check if finding has low value (low confidence AND low severity).

    These are candidates for suppression as they don't provide much value.

    Args:
        finding: The finding to check.
        context: Project context (unused but required for signature).

    Returns:
        True if finding has both low confidence and low severity.
    """
    low_severity = finding.severity.lower() in {'low', 'suggestion', 'info'}
    low_confidence = finding.confidence < 30

    return low_severity and low_confidence


def is_tool_already_catches(finding: Finding, context: "ProjectContext") -> bool:
    """Check if an existing tool already catches this issue.

    If ruff/mypy/etc would flag this, the agent finding is redundant.

    Args:
        finding: The finding to check.
        context: Project context with tool configuration.

    Returns:
        True if an existing tool would catch this.
    """
    # Type annotation issues with mypy configured
    if finding.category.lower() in {'type_annotation', 'typing'}:
        if context.python_config.mypy_configured.value:
            return True

    # Linting issues with ruff configured
    if finding.category.lower() in {'lint', 'style', 'code_quality'}:
        if context.python_config.ruff_rules:
            return True

    return False


# =============================================================================
# FILTER RULES
# =============================================================================

# Filter rules are (predicate, action, reason, confidence_value, reason_code, rule_id) tuples
# The action can be SUPPRESS or SET_CONFIDENCE(value)
FilterRule = Tuple[PredicateFn, FilterAction, str, Optional[int], Optional[SuppressionReasonCode], Optional[str]]


# =============================================================================
# LEARNED PATTERN PREDICATES
# =============================================================================

def make_pattern_predicate(pattern_name: str, category: str) -> PredicateFn:
    """Create a predicate function for a learned pattern.

    Args:
        pattern_name: Name of the learned pattern.
        category: Category to match.

    Returns:
        Predicate function for this pattern.
    """
    def matches_learned_pattern(finding: Finding, context: "ProjectContext") -> bool:
        """Check if finding matches a learned pattern."""
        # Pattern-to-keyword mapping
        pattern_keywords = {
            "sql_orm_handled": ["sql", "orm", "injection", "query"],
            "orm_handled": ["orm", "handled", "database"],
            "tool_ruff_catches": ["ruff", "lint", "format"],
            "tool_mypy_catches": ["mypy", "type", "annotation"],
            "tool_already_catches": ["tool", "catches", "already"],
            "test_fixture": ["test", "fixture", "mock"],
            "test_mock": ["mock", "test", "fake"],
            "internal_helper": ["internal", "helper", "private", "_"],
            "private_function": ["private", "internal", "_"],
            "already_handled": ["already", "handled", "covered"],
            "handled_by_tool": ["handled", "tool", "covered"],
            "style_nitpick": ["style", "naming", "format", "whitespace"],
            "format_nitpick": ["format", "formatting", "whitespace"],
            "naming_nitpick": ["naming", "name", "variable"],
        }

        desc_lower = finding.description.lower()

        # Check category match
        if finding.category.lower() != category.lower():
            return False

        # Check if description matches pattern keywords
        keywords = pattern_keywords.get(pattern_name, [pattern_name.replace("_", " ")])
        matches = sum(1 for kw in keywords if kw in desc_lower)

        # Require at least 2 keyword matches for pattern match
        return matches >= 2

    return matches_learned_pattern


def _load_learned_patterns() -> List[FilterRule]:
    """Load learned patterns from feedback manager.

    Returns:
        List of filter rules created from learned patterns.
    """
    learned_rules = []

    try:
        # Import here to avoid circular dependency
        from feedback_manager import FeedbackManager, FEEDBACK_DIR

        # Check if feedback directory exists
        if not FEEDBACK_DIR.exists():
            return learned_rules

        manager = FeedbackManager()
        calibration = manager.load_calibration()

        for agent_name, agent_cal in calibration.get("agent_calibrations", {}).items():
            for pattern_data in agent_cal.get("pattern_learnings", []):
                if pattern_data.get("action") == "suppress":
                    pattern_name = pattern_data.get("pattern", "unknown")
                    category = pattern_data.get("category", "general")
                    count = pattern_data.get("count", 0)

                    # Create predicate for this pattern
                    predicate = make_pattern_predicate(pattern_name, category)

                    learned_rules.append((
                        predicate,
                        FilterAction.SUPPRESS,
                        f"Learned pattern ({count} FPs): {pattern_name}",
                        None,
                        SuppressionReasonCode.L2_LEARNED_PATTERN,
                        f"L2_rule_learned_{pattern_name}",
                    ))
                    logger.debug(f"Loaded learned pattern: {pattern_name} for {agent_name}")

    except ImportError as e:
        logger.info(f"Feedback manager not available, skipping learned patterns: {e}")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Feedback data corrupted, skipping learned patterns: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading learned patterns: {e}", exc_info=True)

    return learned_rules


def _get_default_filter_rules() -> List[FilterRule]:
    """Get the default set of filter rules including learned patterns.

    Returns:
        List of (predicate, action, reason, confidence_value, reason_code, rule_id) tuples.
    """
    default_rules = [
        # Shell strict mode: error handling is covered
        (
            is_shell_strict_mode,
            FilterAction.SUPPRESS,
            "Shell strict mode (set -euo pipefail) already handles this",
            None,
            SuppressionReasonCode.L2_SHELL_STRICT_MODE,
            "L2_rule_shell_strict",
        ),

        # Style nitpicks: suppress low-severity style issues
        (
            is_style_nitpick,
            FilterAction.SUPPRESS,
            "Style nitpick - not actionable",
            None,
            SuppressionReasonCode.L2_STYLE_NITPICK,
            "L2_rule_style",
        ),

        # Internal helpers without strict mypy: suppress type annotation findings
        (
            is_internal_helper,
            FilterAction.SUPPRESS,
            "Internal helper - mypy not in strict mode",
            None,
            SuppressionReasonCode.L2_INTERNAL_HELPER,
            "L2_rule_internal",
        ),

        # Low value findings: suppress
        (
            is_low_value_finding,
            FilterAction.SUPPRESS,
            "Low value (low confidence + low severity)",
            None,
            SuppressionReasonCode.L2_LOW_VALUE,
            "L2_rule_low_value",
        ),

        # Tool already catches: suppress (redundant)
        (
            is_tool_already_catches,
            FilterAction.SUPPRESS,
            "Existing tool already catches this",
            None,
            SuppressionReasonCode.L2_TOOL_ALREADY_CATCHES,
            "L2_rule_tool_catches",
        ),

        # Optional enhancements: reduce confidence (not suppress)
        (
            is_optional_enhancement,
            FilterAction.SET_CONFIDENCE,
            "Optional enhancement - reduced confidence",
            35,
            SuppressionReasonCode.L2_OPTIONAL_ENHANCEMENT,
            "L2_rule_optional",
        ),

        # Pre-existing issues: reduce confidence significantly
        (
            is_pre_existing_issue,
            FilterAction.SET_CONFIDENCE,
            "Pre-existing code - focus on new changes",
            20,
            SuppressionReasonCode.L2_PRE_EXISTING_CODE,
            "L2_rule_pre_existing",
        ),
    ]

    # Add learned patterns from feedback
    learned_rules = _load_learned_patterns()
    if learned_rules:
        logger.info(f"Added {len(learned_rules)} learned filter rules")
        default_rules.extend(learned_rules)

    return default_rules


# =============================================================================
# FILTER RESULT
# =============================================================================

@dataclass(frozen=True)
class FilteredFinding:
    """A finding after filtering has been applied.

    Attributes:
        finding: The original finding.
        action: What action was taken (SUPPRESS or SET_CONFIDENCE).
        reason: Human-readable reason for the action.
        filtered_confidence: The confidence after filtering.
        reason_code: Canonical reason code (L2_* or L3_*).
        filter_rule_id: Identifier for the filter rule that matched (e.g., "L2_rule_shell_strict").
    """
    finding: Finding
    action: FilterAction
    reason: str
    filtered_confidence: int
    reason_code: Optional[SuppressionReasonCode] = None
    filter_rule_id: Optional[str] = None

    @property
    def is_suppressed(self) -> bool:
        """Check if this finding was suppressed."""
        return self.action == FilterAction.SUPPRESS


# =============================================================================
# FINDING FILTER CLASS
# =============================================================================

class FindingFilter:
    """Filter findings based on project context and typed predicates.

    This class applies Layer 2 filtering to reduce false positives.
    It uses typed predicate functions (not string DSLs) for reliability.

    Example:
        >>> context = build_project_context()
        >>> filter = FindingFilter(context)
        >>> filtered = filter.filter_findings(all_findings)
        >>> for f in filtered:
        ...     if f.is_suppressed:
        ...         print(f"Suppressed: {f.reason}")
    """

    def __init__(
        self,
        context: "ProjectContext",
        filter_rules: Optional[List[FilterRule]] = None
    ):
        """Initialize the filter.

        Args:
            context: Project context with configuration.
            filter_rules: Optional custom filter rules (uses defaults if None).
        """
        self.context = context
        self.filter_rules = filter_rules or _get_default_filter_rules()

    def filter_finding(self, finding: Finding) -> FilteredFinding:
        """Apply filter rules to a single finding.

        Rules are applied in order; first matching rule wins.

        Args:
            finding: The finding to filter.

        Returns:
            FilteredFinding with action, reason, filtered confidence, and reason code.
        """
        for rule in self.filter_rules:
            # Unpack rule based on length (support both old 4-tuple and new 6-tuple)
            if len(rule) == 6:
                predicate, action, reason, confidence_value, reason_code, rule_id = rule
            else:
                predicate, action, reason, confidence_value = rule
                reason_code = None
                rule_id = None

            try:
                if predicate(finding, self.context):
                    if action == FilterAction.SUPPRESS:
                        logger.debug(
                            f"Suppressing finding {finding.id}: {reason}"
                        )
                        return FilteredFinding(
                            finding=finding,
                            action=action,
                            reason=reason,
                            filtered_confidence=0,
                            reason_code=reason_code,
                            filter_rule_id=rule_id,
                        )
                    elif action == FilterAction.SET_CONFIDENCE:
                        new_confidence = confidence_value if confidence_value is not None else finding.confidence
                        # Ensure minimum confidence of 25 (never suppress via confidence)
                        new_confidence = max(25, min(100, new_confidence))
                        logger.debug(
                            f"Adjusting finding {finding.id} confidence: "
                            f"{finding.confidence} -> {new_confidence}: {reason}"
                        )
                        return FilteredFinding(
                            finding=finding,
                            action=action,
                            reason=reason,
                            filtered_confidence=new_confidence,
                            reason_code=reason_code,
                            filter_rule_id=rule_id,
                        )
            except Exception as e:
                logger.warning(
                    f"Error applying filter rule to {finding.id}: {e}"
                )
                continue

        # No rule matched - keep original
        return FilteredFinding(
            finding=finding,
            action=FilterAction.SET_CONFIDENCE,
            reason="No filter rule matched",
            filtered_confidence=finding.confidence,
            reason_code=None,
            filter_rule_id=None,
        )

    def filter_findings(self, findings: List[Finding]) -> List[FilteredFinding]:
        """Apply filter rules to multiple findings.

        Args:
            findings: List of findings to filter.

        Returns:
            List of FilteredFindings (including suppressed ones).
        """
        return [self.filter_finding(f) for f in findings]

    def get_active_findings(self, findings: List[Finding]) -> List[FilteredFinding]:
        """Get only non-suppressed findings.

        Args:
            findings: List of findings to filter.

        Returns:
            List of FilteredFindings that were not suppressed.
        """
        all_filtered = self.filter_findings(findings)
        return [f for f in all_filtered if not f.is_suppressed]

    def get_suppressed_findings(self, findings: List[Finding]) -> List[FilteredFinding]:
        """Get only suppressed findings (for reporting).

        Args:
            findings: List of findings to filter.

        Returns:
            List of suppressed FilteredFindings with reasons.
        """
        all_filtered = self.filter_findings(findings)
        return [f for f in all_filtered if f.is_suppressed]

    def categorize_findings(
        self,
        findings: List[Finding]
    ) -> Dict[str, List[FilteredFinding]]:
        """Categorize findings by severity and filtered confidence.

        Categories:
            - critical: confidence 75-100
            - important: confidence 50-74
            - suggestions: confidence 25-49
            - suppressed: filtered out (reasons included)

        Args:
            findings: List of findings to filter and categorize.

        Returns:
            Dictionary with categorized findings.
        """
        filtered = self.filter_findings(findings)

        categories = {
            "critical": [],
            "important": [],
            "suggestions": [],
            "suppressed": [],
        }

        for f in filtered:
            if f.is_suppressed:
                categories["suppressed"].append(f)
            elif f.filtered_confidence >= 75:
                categories["critical"].append(f)
            elif f.filtered_confidence >= 50:
                categories["important"].append(f)
            else:
                categories["suggestions"].append(f)

        return categories

    def get_summary(self, findings: List[Finding]) -> Dict[str, Any]:
        """Get summary statistics for filtered findings.

        Args:
            findings: List of findings to filter.

        Returns:
            Dictionary with counts per category.
        """
        categories = self.categorize_findings(findings)

        # Count suppression reasons
        suppression_reasons: Dict[str, int] = {}
        for f in categories["suppressed"]:
            reason = f.reason
            suppression_reasons[reason] = suppression_reasons.get(reason, 0) + 1

        return {
            "total_findings": len(findings),
            "active_findings": sum(
                len(categories[k]) for k in ["critical", "important", "suggestions"]
            ),
            "suppressed_findings": len(categories["suppressed"]),
            "critical": len(categories["critical"]),
            "important": len(categories["important"]),
            "suggestions": len(categories["suggestions"]),
            "suppression_reasons": suppression_reasons,
            "filter_effectiveness": (
                len(categories["suppressed"]) / len(findings) * 100
                if findings else 0
            ),
        }
