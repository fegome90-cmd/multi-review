#!/usr/bin/env python3
"""
Unit tests for finding_filter.py.

Tests for:
- FilterAction enum
- Finding dataclass
- Typed predicate functions
- FindingFilter class
- Golden tests (input -> output)
"""

import pytest
from pathlib import Path
from dataclasses import FrozenInstanceError

# Add scripts to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from finding_filter import (
    FilterAction,
    Finding,
    FilteredFinding,
    FindingFilter,
    is_shell_strict_mode,
    is_style_nitpick,
    is_optional_enhancement,
    is_internal_helper,
    is_low_value_finding,
    is_tool_already_catches,
)

# Import ProjectContext for testing
from project_context import (
    ConfigValue,
    EvidenceLevel,
    PythonConfig,
    ShellConfig,
    TestConfig,
    GitMetadata,
    ProjectContext,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def default_context():
    """Create a default ProjectContext for testing."""
    return ProjectContext.default()


@pytest.fixture
def strict_shell_context():
    """Create a context with shell strict mode enabled."""
    shell_config = ShellConfig(
        strict_mode_files=frozenset([Path("script.sh")]),
        detection_evidence=frozenset(["script.sh:1:set -euo pipefail"]),
        has_any_shell_scripts=ConfigValue(True, EvidenceLevel.FACT, "found"),
    )
    return ProjectContext(
        python_config=PythonConfig.default(),
        shell_config=shell_config,
        test_config=TestConfig.default(),
        git_metadata=GitMetadata.default(),
    )


@pytest.fixture
def mypy_strict_context():
    """Create a context with mypy strict mode enabled."""
    python_config = PythonConfig(
        mypy_strict=ConfigValue(True, EvidenceLevel.FACT, "mypy.ini"),
        mypy_configured=ConfigValue(True, EvidenceLevel.FACT, "mypy.ini"),
        ruff_rules=frozenset(),
        type_checking_level=ConfigValue("strict", EvidenceLevel.FACT, "mypy.ini"),
        uses_result_pattern=ConfigValue(False, EvidenceLevel.ASSUMPTION, "none"),
    )
    return ProjectContext(
        python_config=python_config,
        shell_config=ShellConfig.default(),
        test_config=TestConfig.default(),
        git_metadata=GitMetadata.default(),
    )


@pytest.fixture
def sample_finding():
    """Create a sample finding for testing."""
    return Finding(
        id="test-001",
        file="src/main.py",
        line=42,
        category="error_handling",
        severity="Important",
        confidence=75,
        description="Missing error handling for API call",
        source_agent="test-agent",
    )


# =============================================================================
# TEST FILTERACTION
# =============================================================================

class TestFilterAction:
    """Tests for FilterAction enum."""

    def test_filter_action_values(self):
        """Test that FilterAction has correct values."""
        assert FilterAction.SUPPRESS.value == "suppress"
        assert FilterAction.SET_CONFIDENCE.value == "set_confidence"

    def test_filter_action_count(self):
        """Test that there are exactly 2 filter actions."""
        assert len(FilterAction) == 2


# =============================================================================
# TEST FINDING
# =============================================================================

class TestFinding:
    """Tests for Finding dataclass."""

    def test_finding_creation(self):
        """Test creating a Finding."""
        finding = Finding(
            id="test-001",
            file="src/main.py",
            line=42,
            category="error_handling",
            severity="Critical",
            confidence=85,
            description="Test issue",
        )
        assert finding.id == "test-001"
        assert finding.file == "src/main.py"
        assert finding.line == 42
        assert finding.confidence == 85

    def test_finding_immutability(self):
        """Test that Finding is immutable."""
        finding = Finding(
            id="test-001",
            file="src/main.py",
            line=42,
            category="test",
            severity="Low",
            confidence=50,
            description="Test",
        )
        with pytest.raises(FrozenInstanceError):
            finding.confidence = 100

    def test_finding_confidence_validation(self):
        """Test that confidence must be 0-100."""
        # Valid confidence
        Finding(
            id="test",
            file="test.py",
            line=1,
            category="test",
            severity="Low",
            confidence=0,
            description="Test",
        )
        Finding(
            id="test",
            file="test.py",
            line=1,
            category="test",
            severity="Low",
            confidence=100,
            description="Test",
        )

        # Invalid confidence
        with pytest.raises(ValueError):
            Finding(
                id="test",
                file="test.py",
                line=1,
                category="test",
                severity="Low",
                confidence=-1,
                description="Test",
            )
        with pytest.raises(ValueError):
            Finding(
                id="test",
                file="test.py",
                line=1,
                category="test",
                severity="Low",
                confidence=101,
                description="Test",
            )

    def test_finding_file_required(self):
        """Test that file path cannot be empty."""
        with pytest.raises(ValueError):
            Finding(
                id="test",
                file="",
                line=1,
                category="test",
                severity="Low",
                confidence=50,
                description="Test",
            )

    def test_finding_line_non_negative(self):
        """Test that line number must be >= 0."""
        with pytest.raises(ValueError):
            Finding(
                id="test",
                file="test.py",
                line=-1,
                category="test",
                severity="Low",
                confidence=50,
                description="Test",
            )


# =============================================================================
# TEST PREDICATES
# =============================================================================

class TestIsShellStrictMode:
    """Tests for is_shell_strict_mode predicate."""

    def test_not_shell_file(self, default_context):
        """Test that non-shell files return False."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="error_handling",
            severity="Low",
            confidence=50,
            description="Error handling issue",
        )
        assert is_shell_strict_mode(finding, default_context) is False

    def test_shell_file_no_strict_mode(self, default_context):
        """Test shell file without strict mode returns False."""
        finding = Finding(
            id="test",
            file="script.sh",
            line=1,
            category="error_handling",
            severity="Low",
            confidence=50,
            description="Error handling issue",
        )
        assert is_shell_strict_mode(finding, default_context) is False

    def test_shell_file_with_strict_mode(self, strict_shell_context):
        """Test shell file with strict mode returns True for error handling."""
        finding = Finding(
            id="test",
            file="script.sh",
            line=1,
            category="error_handling",
            severity="Low",
            confidence=50,
            description="Missing error handling",
        )
        assert is_shell_strict_mode(finding, strict_shell_context) is True

    def test_shell_file_with_strict_mode_other_category(self, strict_shell_context):
        """Test shell file with strict mode returns False for other categories."""
        finding = Finding(
            id="test",
            file="script.sh",
            line=1,
            category="style",
            severity="Low",
            confidence=50,
            description="Style issue",
        )
        assert is_shell_strict_mode(finding, strict_shell_context) is False

    def test_shell_file_error_description(self, strict_shell_context):
        """Test shell file with error-related description."""
        finding = Finding(
            id="test",
            file="script.sh",
            line=1,
            category="general",
            severity="Low",
            confidence=50,
            description="Should check exit code",
        )
        assert is_shell_strict_mode(finding, strict_shell_context) is True


class TestIsStyleNitpick:
    """Tests for is_style_nitpick predicate."""

    def test_not_low_severity(self, default_context):
        """Test that non-low severity returns False."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="style",
            severity="Important",
            confidence=50,
            description="Naming issue",
        )
        assert is_style_nitpick(finding, default_context) is False

    def test_low_severity_nitpick_term(self, default_context):
        """Test low severity with nitpick term returns True."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="style",
            severity="Low",
            confidence=50,
            description="Variable naming could be improved",
        )
        assert is_style_nitpick(finding, default_context) is True

    def test_low_severity_formatting(self, default_context):
        """Test low severity formatting issue."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="style",
            severity="Low",
            confidence=50,
            description="Formatting issue",
        )
        assert is_style_nitpick(finding, default_context) is True

    def test_low_severity_not_nitpick(self, default_context):
        """Test low severity without nitpick term."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="error_handling",
            severity="Low",
            confidence=50,
            description="Critical bug in error path",
        )
        assert is_style_nitpick(finding, default_context) is False


class TestIsOptionalEnhancement:
    """Tests for is_optional_enhancement predicate."""

    def test_could_term(self, default_context):
        """Test 'could' term detection."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="general",
            severity="Low",
            confidence=50,
            description="Could add type annotation",
        )
        assert is_optional_enhancement(finding, default_context) is True

    def test_might_term(self, default_context):
        """Test 'might' term detection."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="general",
            severity="Low",
            confidence=50,
            description="Might want to refactor this",
        )
        assert is_optional_enhancement(finding, default_context) is True

    def test_consider_term(self, default_context):
        """Test 'consider' term detection."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="general",
            severity="Low",
            confidence=50,
            description="Consider using a constant",
        )
        assert is_optional_enhancement(finding, default_context) is True

    def test_required_issue(self, default_context):
        """Test required issue (not optional)."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="security",
            severity="Critical",
            confidence=90,
            description="SQL injection vulnerability",
        )
        assert is_optional_enhancement(finding, default_context) is False


class TestIsInternalHelper:
    """Tests for is_internal_helper predicate."""

    def test_not_type_annotation(self, default_context):
        """Test non-type-annotation category returns False."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="error_handling",
            severity="Low",
            confidence=50,
            description="Internal helper error",
        )
        assert is_internal_helper(finding, default_context) is False

    def test_type_annotation_with_strict_mypy(self, mypy_strict_context):
        """Test type annotation with mypy strict mode returns False."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="type_annotation",
            severity="Low",
            confidence=50,
            description="Missing type annotation for _helper",
        )
        # Should NOT suppress if mypy is strict
        assert is_internal_helper(finding, mypy_strict_context) is False

    def test_type_annotation_internal_no_strict(self, default_context):
        """Test type annotation for internal helper without strict mypy."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="type_annotation",
            severity="Low",
            confidence=50,
            description="Missing type annotation for _helper function",
        )
        # Should suppress if mypy is not strict
        assert is_internal_helper(finding, default_context) is True


class TestIsLowValueFinding:
    """Tests for is_low_value_finding predicate."""

    def test_low_severity_low_confidence(self, default_context):
        """Test low severity + low confidence."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="general",
            severity="Low",
            confidence=20,
            description="Minor issue",
        )
        assert is_low_value_finding(finding, default_context) is True

    def test_low_severity_high_confidence(self, default_context):
        """Test low severity + high confidence."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="general",
            severity="Low",
            confidence=80,
            description="Confirmed issue",
        )
        assert is_low_value_finding(finding, default_context) is False

    def test_high_severity_low_confidence(self, default_context):
        """Test high severity + low confidence."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="general",
            severity="Critical",
            confidence=20,
            description="Potential issue",
        )
        assert is_low_value_finding(finding, default_context) is False


class TestIsToolAlreadyCatches:
    """Tests for is_tool_already_catches predicate."""

    def test_type_annotation_mypy_configured(self):
        """Test type annotation with mypy configured."""
        python_config = PythonConfig(
            mypy_strict=ConfigValue(False, EvidenceLevel.FACT, "config"),
            mypy_configured=ConfigValue(True, EvidenceLevel.FACT, "config"),
            ruff_rules=frozenset(),
            type_checking_level=ConfigValue("relaxed", EvidenceLevel.FACT, "config"),
            uses_result_pattern=ConfigValue(False, EvidenceLevel.ASSUMPTION, "none"),
        )
        context = ProjectContext(
            python_config=python_config,
            shell_config=ShellConfig.default(),
            test_config=TestConfig.default(),
            git_metadata=GitMetadata.default(),
        )
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="type_annotation",
            severity="Low",
            confidence=50,
            description="Missing type hint",
        )
        assert is_tool_already_catches(finding, context) is True

    def test_type_annotation_no_mypy(self, default_context):
        """Test type annotation without mypy configured."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="type_annotation",
            severity="Low",
            confidence=50,
            description="Missing type hint",
        )
        assert is_tool_already_catches(finding, default_context) is False


# =============================================================================
# TEST FINDINGFILTER
# =============================================================================

class TestFindingFilter:
    """Tests for FindingFilter class."""

    def test_filter_creation(self, default_context):
        """Test creating a FindingFilter."""
        filter = FindingFilter(default_context)
        assert filter.context == default_context

    def test_filter_single_finding_no_match(self, default_context, sample_finding):
        """Test filtering a finding that matches no rules."""
        filter = FindingFilter(default_context)
        result = filter.filter_finding(sample_finding)

        assert result.action == FilterAction.SET_CONFIDENCE
        assert result.filtered_confidence == sample_finding.confidence
        assert not result.is_suppressed

    def test_filter_suppress_style_nitpick(self, default_context):
        """Test suppressing a style nitpick."""
        finding = Finding(
            id="test",
            file="src/main.py",
            line=1,
            category="style",
            severity="Low",
            confidence=50,
            description="Variable naming could be improved",
        )
        filter = FindingFilter(default_context)
        result = filter.filter_finding(finding)

        assert result.is_suppressed
        assert "nitpick" in result.reason.lower()

    def test_filter_multiple_findings(self, default_context):
        """Test filtering multiple findings."""
        findings = [
            Finding(
                id="test-1",
                file="src/main.py",
                line=1,
                category="error_handling",
                severity="Critical",
                confidence=90,
                description="Critical bug",
            ),
            Finding(
                id="test-2",
                file="src/main.py",
                line=2,
                category="style",
                severity="Low",
                confidence=30,
                description="Naming could be better",
            ),
        ]
        filter = FindingFilter(default_context)
        results = filter.filter_findings(findings)

        assert len(results) == 2
        assert not results[0].is_suppressed  # Critical bug kept
        assert results[1].is_suppressed  # Style nitpick suppressed

    def test_get_active_findings(self, default_context):
        """Test getting only active (non-suppressed) findings."""
        findings = [
            Finding(
                id="test-1",
                file="src/main.py",
                line=1,
                category="error_handling",
                severity="Critical",
                confidence=90,
                description="Critical bug",
            ),
            Finding(
                id="test-2",
                file="src/main.py",
                line=2,
                category="style",
                severity="Low",
                confidence=30,
                description="Naming could be better",
            ),
        ]
        filter = FindingFilter(default_context)
        active = filter.get_active_findings(findings)

        assert len(active) == 1
        assert active[0].finding.id == "test-1"

    def test_get_suppressed_findings(self, default_context):
        """Test getting only suppressed findings."""
        findings = [
            Finding(
                id="test-1",
                file="src/main.py",
                line=1,
                category="error_handling",
                severity="Critical",
                confidence=90,
                description="Critical bug",
            ),
            Finding(
                id="test-2",
                file="src/main.py",
                line=2,
                category="style",
                severity="Low",
                confidence=30,
                description="Naming could be better",
            ),
        ]
        filter = FindingFilter(default_context)
        suppressed = filter.get_suppressed_findings(findings)

        assert len(suppressed) == 1
        assert suppressed[0].finding.id == "test-2"

    def test_categorize_findings(self, default_context):
        """Test categorizing findings by filtered confidence."""
        findings = [
            Finding(
                id="critical",
                file="src/main.py",
                line=1,
                category="error_handling",
                severity="Critical",
                confidence=90,
                description="Critical bug",
            ),
            Finding(
                id="important",
                file="src/main.py",
                line=2,
                category="error_handling",
                severity="Important",
                confidence=60,
                description="Important issue",
            ),
            Finding(
                id="suggestion",
                file="src/main.py",
                line=3,
                category="general",
                severity="Low",
                confidence=35,
                description="Suggestion",
            ),
        ]
        filter = FindingFilter(default_context)
        categories = filter.categorize_findings(findings)

        assert len(categories["critical"]) == 1
        assert len(categories["important"]) == 1
        assert len(categories["suggestions"]) == 1

    def test_get_summary(self, default_context):
        """Test getting filter summary."""
        findings = [
            Finding(
                id="test-1",
                file="src/main.py",
                line=1,
                category="error_handling",
                severity="Critical",
                confidence=90,
                description="Critical bug",
            ),
            Finding(
                id="test-2",
                file="src/main.py",
                line=2,
                category="style",
                severity="Low",
                confidence=30,
                description="Naming could be better",
            ),
        ]
        filter = FindingFilter(default_context)
        summary = filter.get_summary(findings)

        assert summary["total_findings"] == 2
        assert summary["active_findings"] == 1
        assert summary["suppressed_findings"] == 1
        assert summary["filter_effectiveness"] == 50.0

    def test_shell_strict_mode_suppression(self, strict_shell_context):
        """Test that shell strict mode findings are suppressed."""
        finding = Finding(
            id="test",
            file="script.sh",
            line=1,
            category="error_handling",
            severity="Low",
            confidence=50,
            description="Missing error check",
        )
        filter = FindingFilter(strict_shell_context)
        result = filter.filter_finding(finding)

        assert result.is_suppressed
        assert "strict mode" in result.reason.lower()


# =============================================================================
# GOLDEN TESTS (Input -> Output)
# =============================================================================

class TestGoldenTests:
    """Golden tests verifying expected input -> output behavior."""

    def test_golden_shell_strict_mode(self, strict_shell_context):
        """Golden test: Shell strict mode should suppress error handling findings."""
        findings = [
            Finding(
                id="shell-error-1",
                file="script.sh",
                line=10,
                category="error_handling",
                severity="Important",
                confidence=70,
                description="Missing error handling for command",
            ),
        ]

        filter = FindingFilter(strict_shell_context)
        results = filter.filter_findings(findings)

        # Expected: suppressed because shell has strict mode
        assert len(results) == 1
        assert results[0].is_suppressed
        assert "strict mode" in results[0].reason.lower()

    def test_golden_style_nitpick_chain(self, default_context):
        """Golden test: Multiple style nitpicks should all be suppressed."""
        findings = [
            Finding(
                id="style-1",
                file="src/main.py",
                line=10,
                category="style",
                severity="Low",
                confidence=40,
                description="Variable naming could be improved",
            ),
            Finding(
                id="style-2",
                file="src/main.py",
                line=20,
                category="style",
                severity="Low",
                confidence=35,
                description="Formatting inconsistency",
            ),
            Finding(
                id="style-3",
                file="src/main.py",
                line=30,
                category="style",
                severity="Low",
                confidence=30,
                description="Redundant parentheses",
            ),
        ]

        filter = FindingFilter(default_context)
        results = filter.filter_findings(findings)

        # Expected: all suppressed
        assert all(r.is_suppressed for r in results)

    def test_golden_mixed_findings(self, default_context):
        """Golden test: Mixed findings should be correctly categorized."""
        findings = [
            # Critical - should be kept (confidence >= 75 -> critical)
            Finding(
                id="critical-1",
                file="src/auth.py",
                line=42,
                category="security",
                severity="Critical",
                confidence=95,
                description="SQL injection vulnerability",
            ),
            # Style nitpick - should be suppressed
            Finding(
                id="style-1",
                file="src/utils.py",
                line=10,
                category="style",
                severity="Low",
                confidence=30,
                description="Variable naming",
            ),
            # Optional enhancement - confidence should be reduced to 35
            Finding(
                id="enhancement-1",
                file="src/api.py",
                line=100,
                category="general",
                severity="Low",
                confidence=50,
                description="Could add caching for performance",
            ),
            # Important - should be kept (confidence 50-74 -> important)
            Finding(
                id="important-1",
                file="src/api.py",
                line=200,
                category="error_handling",
                severity="Important",
                confidence=65,
                description="Missing error handling for timeout",
            ),
        ]

        filter = FindingFilter(default_context)
        categories = filter.categorize_findings(findings)

        # Expected: 1 critical (95), 1 important (35 after reduction + 65 = 2 in suggestions)
        # Actually: enhancement goes to suggestions (35), important stays important (65)
        assert len(categories["critical"]) == 1
        assert len(categories["important"]) == 1  # 65 -> important
        assert len(categories["suggestions"]) == 1  # 35 -> suggestions
        assert len(categories["suppressed"]) == 1  # style nitpick
