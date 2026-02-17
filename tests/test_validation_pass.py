#!/usr/bin/env python3
"""
Tests for validation_pass module.

Run with: pytest tests/test_validation_pass.py -v
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from validation_pass import (
    Evidence,
    ValidationMode,
    parse_ruff_output,
    parse_mypy_output,
    ValidationPass,
)
from finding_filter import Finding


class TestEvidence:
    """Tests for Evidence dataclass."""

    def test_create_evidence(self):
        """Test creating evidence."""
        evidence = Evidence(
            source="ruff",
            file="src/auth.py",
            line=45,
            message="Unused import",
            severity="warning",
            code="F401",
        )

        assert evidence.source == "ruff"
        assert evidence.file == "src/auth.py"
        assert evidence.line == 45
        assert evidence.code == "F401"

    def test_evidence_immutability(self):
        """Test evidence is immutable."""
        evidence = Evidence(
            source="test",
            file="test.py",
            line=1,
            message="test",
            severity="warning",
        )

        with pytest.raises(Exception):
            evidence.line = 2

    def test_matches_finding_same_file_line(self):
        """Test matching finding with same file and line."""
        evidence = Evidence(
            source="ruff",
            file="src/auth.py",
            line=45,
            message="Test",
            severity="warning",
        )

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=45,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
            source_agent="test",
        )

        assert evidence.matches_finding(finding) is True

    def test_matches_finding_different_file(self):
        """Test non-matching finding with different file."""
        evidence = Evidence(
            source="ruff",
            file="src/auth.py",
            line=45,
            message="Test",
            severity="warning",
        )

        finding = Finding(
            id="test-1",
            file="src/other.py",
            line=45,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
            source_agent="test",
        )

        assert evidence.matches_finding(finding) is False

    def test_matches_finding_line_tolerance(self):
        """Test matching with line tolerance."""
        evidence = Evidence(
            source="ruff",
            file="src/auth.py",
            line=45,
            message="Test",
            severity="warning",
        )

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=47,  # 2 lines away
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
            source_agent="test",
        )

        # Default tolerance is 2
        assert evidence.matches_finding(finding, line_tolerance=2) is True
        assert evidence.matches_finding(finding, line_tolerance=1) is False

    def test_matches_finding_no_line(self):
        """Test matching when evidence has no line."""
        evidence = Evidence(
            source="ruff",
            file="src/auth.py",
            line=None,
            message="File-level issue",
            severity="warning",
        )

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=45,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
            source_agent="test",
        )

        assert evidence.matches_finding(finding) is True


class TestValidationMode:
    """Tests for ValidationMode enum."""

    def test_mode_values(self):
        """Test mode enum values."""
        assert ValidationMode.FAST.value == "fast"
        assert ValidationMode.EVIDENCE.value == "evidence"


class TestParseRuffOutput:
    """Tests for parse_ruff_output function."""

    def test_parse_single_issue(self):
        """Test parsing single ruff issue."""
        output = "src/auth.py:10:5: F401 `os` imported but unused"

        evidence = parse_ruff_output(output, "src/auth.py")

        assert len(evidence) == 1
        assert evidence[0].source == "ruff"
        assert evidence[0].line == 10
        assert evidence[0].code == "F401"
        assert "imported but unused" in evidence[0].message

    def test_parse_multiple_issues(self):
        """Test parsing multiple ruff issues."""
        output = """src/auth.py:10:5: F401 `os` imported but unused
src/auth.py:20:1: E501 line too long"""

        evidence = parse_ruff_output(output, "src/auth.py")

        assert len(evidence) == 2
        assert evidence[0].line == 10
        assert evidence[1].line == 20

    def test_parse_with_fixable_marker(self):
        """Test parsing with [*] fixable marker."""
        output = "src/auth.py:10:5: F401 [*] `os` imported but unused"

        evidence = parse_ruff_output(output, "src/auth.py")

        assert len(evidence) == 1
        assert "[*]" not in evidence[0].message

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        evidence = parse_ruff_output("", "src/auth.py")
        assert evidence == []

    def test_parse_found_summary_ignored(self):
        """Test that 'Found X errors' summary is ignored."""
        output = """src/auth.py:10:5: F401 `os` imported but unused
Found 1 error"""

        evidence = parse_ruff_output(output, "src/auth.py")

        assert len(evidence) == 1


class TestParseMypyOutput:
    """Tests for parse_mypy_output function."""

    def test_parse_error(self):
        """Test parsing mypy error."""
        output = "src/auth.py:10: error: Incompatible types in assignment"

        evidence = parse_mypy_output(output, "src/auth.py")

        assert len(evidence) == 1
        assert evidence[0].source == "mypy"
        assert evidence[0].line == 10
        assert evidence[0].severity == "error"

    def test_parse_warning(self):
        """Test parsing mypy warning."""
        output = "src/auth.py:10: warning: Unused ignore comment"

        evidence = parse_mypy_output(output, "src/auth.py")

        assert len(evidence) == 1
        assert evidence[0].severity == "warning"

    def test_parse_note(self):
        """Test parsing mypy note."""
        output = "src/auth.py:10: note: Consider explicit type"

        evidence = parse_mypy_output(output, "src/auth.py")

        assert len(evidence) == 1
        assert evidence[0].severity == "warning"  # note -> warning

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        evidence = parse_mypy_output("", "src/auth.py")
        assert evidence == []

    def test_parse_multiple_issues(self):
        """Test parsing multiple mypy issues."""
        output = """src/auth.py:10: error: Incompatible types
src/auth.py:20: warning: Unused ignore"""

        evidence = parse_mypy_output(output, "src/auth.py")

        assert len(evidence) == 2
        assert evidence[0].severity == "error"
        assert evidence[1].severity == "warning"


class TestValidationPass:
    """Tests for ValidationPass class."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.python_config.mypy_configured.value = True
        context.python_config.ruff_rules = ["E501", "F401"]
        return context

    def test_initialization(self, mock_context):
        """Test ValidationPass initialization."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        assert validation.mode == ValidationMode.FAST
        assert validation._evidence_cache == {}

    def test_validate_finding_fast_mode(self, mock_context):
        """Test validating finding in fast mode."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
            source_agent="test",
        )

        # In fast mode with no cached evidence, should return finding unchanged
        validated = validation.validate_finding(finding)
        assert validated.file == "src/auth.py"

    def test_validate_findings_batch(self, mock_context):
        """Test validating multiple findings."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        findings = [
            Finding(
                id=f"test-{i}",
                file="src/auth.py",
                line=10 + i,
                category="style",
                severity="Low",
                confidence=50,
                description=f"Test finding {i}",
                source_agent="test",
            )
            for i in range(3)
        ]

        validated = validation.validate_findings(findings)
        assert len(validated) == 3


class TestRunTools:
    """Tests for _run_tools method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.python_config.mypy_configured.value = True
        context.python_config.mypy_strict.value = False
        context.python_config.uses_result_pattern.value = False
        context.shell_config.strict_mode_files = set()
        context.python_config.ruff_rules = ["E501", "F401"]
        return context

    @patch("validation_pass.subprocess.run")
    def test_run_tools_for_file_ruff_success(self, mock_run, mock_context):
        """Test _run_tools_for_file with successful ruff execution."""
        mock_run.return_value = Mock(
            stdout="src/auth.py:10:5: F401 `os` imported but unused", returncode=1
        )

        validation = ValidationPass(mock_context, ValidationMode.EVIDENCE)
        evidence = validation._run_tools("src/auth.py")

        assert len(evidence) >= 1
        assert evidence[0].source == "ruff"
        assert evidence[0].line == 10
        assert evidence[0].code == "F401"

    @patch("validation_pass.subprocess.run")
    def test_run_tools_for_file_ruff_not_found(self, mock_run, mock_context):
        """Test _run_tools_for_file with FileNotFoundError when ruff not installed."""
        mock_run.side_effect = FileNotFoundError("ruff not found")

        validation = ValidationPass(mock_context, ValidationMode.EVIDENCE)
        evidence = validation._run_tools("src/auth.py")

        # Should return empty list when ruff not found
        assert evidence == []

    @patch("validation_pass.subprocess.run")
    def test_run_tools_for_file_timeout_expired(self, mock_run, mock_context):
        """Test _run_tools_for_file with TimeoutExpired handling."""
        mock_run.side_effect = subprocess.TimeoutExpired("ruff", 30)

        validation = ValidationPass(mock_context, ValidationMode.EVIDENCE)
        evidence = validation._run_tools("src/auth.py")

        # Should return empty list when timeout occurs
        assert evidence == []

    @patch("validation_pass.subprocess.run")
    def test_run_tools_for_file_mypy_configured(self, mock_run, mock_context):
        """Test _run_tools_for_file runs mypy when mypy_configured=True."""
        mock_run.return_value = Mock(
            stdout="src/auth.py:10: error: Incompatible types", returncode=1
        )

        validation = ValidationPass(mock_context, ValidationMode.EVIDENCE)
        evidence = validation._run_tools("src/auth.py")

        # Should have evidence from both ruff and mypy
        assert len(evidence) >= 2
        sources = {e.source for e in evidence}
        assert "ruff" in sources
        assert "mypy" in sources

    @patch("validation_pass.subprocess.run")
    def test_run_tools_for_file_mypy_not_configured(self, mock_run):
        """Test _run_tools_for_file skips mypy when mypy_configured=False."""
        mock_run.return_value = Mock(
            stdout="src/auth.py:10:5: F401 `os` imported but unused", returncode=1
        )

        context = MagicMock()
        context.python_config.mypy_configured.value = False
        context.python_config.ruff_rules = ["E501", "F401"]

        validation = ValidationPass(context, ValidationMode.EVIDENCE)
        evidence = validation._run_tools("src/auth.py")

        # Should only have ruff evidence, not mypy
        assert len(evidence) >= 1
        sources = {e.source for e in evidence}
        assert "ruff" in sources
        assert "mypy" not in sources


class TestLoadCachedEvidence:
    """Tests for _load_cached_evidence method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.python_config.mypy_configured.value = True
        context.python_config.mypy_strict.value = False
        context.python_config.uses_result_pattern.value = False
        context.shell_config.strict_mode_files = set()
        return context

    @patch("pathlib.Path.exists")
    def test_load_cached_evidence_returns_empty_when_not_exists(
        self, mock_exists, mock_context
    ):
        """Test _load_cached_evidence returns empty list when cache doesn't exist."""
        mock_exists.return_value = False

        validation = ValidationPass(mock_context, ValidationMode.FAST)
        evidence = validation._load_cached_evidence("src/auth.py")

        assert evidence == []

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_load_cached_evidence_handles_corrupted_json(
        self, mock_read, mock_exists, mock_context
    ):
        """Test _load_cached_evidence handles corrupted JSON."""
        mock_exists.return_value = True
        mock_read.return_value = "invalid json {"

        validation = ValidationPass(mock_context, ValidationMode.FAST)
        evidence = validation._load_cached_evidence("src/auth.py")

        # Should return empty list on JSON decode error
        assert evidence == []


class TestToolCatches:
    """Tests for _tool_catches method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.python_config.mypy_configured.value = True
        context.python_config.mypy_strict.value = False
        context.python_config.uses_result_pattern.value = False
        context.shell_config.strict_mode_files = set()
        return context

    def test_tool_catches_with_matching_evidence(self, mock_context):
        """Test _tool_catches with matching evidence."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        evidence = [
            Evidence(
                source="ruff",
                file="src/auth.py",
                line=10,
                message="unused import os",
                severity="warning",
                code="F401",
            )
        ]

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="unused import os",
            source_agent="test",
        )

        result = validation._tool_catches(evidence, finding)
        # Should catch because messages have overlapping terms
        assert result is True

    def test_tool_catches_with_no_matching_evidence(self, mock_context):
        """Test _tool_catches with no matching evidence."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        evidence = [
            Evidence(
                source="ruff",
                file="src/other.py",
                line=10,
                message="line too long",
                severity="warning",
                code="E501",
            )
        ]

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="unused import",
            source_agent="test",
        )

        result = validation._tool_catches(evidence, finding)
        # Should not catch because different file
        assert result is False


class TestToolContradicts:
    """Tests for _tool_contradicts method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.python_config.mypy_configured.value = True
        context.python_config.mypy_strict.value = False
        context.python_config.uses_result_pattern.value = False
        context.shell_config.strict_mode_files = set()
        return context

    def test_tool_contradicts_type_annotation_with_internal(self, mock_context):
        """Test _tool_contradicts with type annotation findings for internal code."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        finding = Finding(
            id="test-1",
            file="src/_internal.py",
            line=10,
            category="type_annotation",
            severity="Low",
            confidence=50,
            description="Missing type annotation in _internal function",
            source_agent="test",
        )

        evidence = []

        result = validation._tool_contradicts(evidence, finding)
        # Should contradict because mypy not strict and internal code
        assert result is True

    def test_tool_contradicts_no_contradiction(self, mock_context):
        """Test _tool_contradicts returns False when no contradiction."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        finding = Finding(
            id="test-1",
            file="src/public.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Code style issue",
            source_agent="test",
        )

        evidence = []

        result = validation._tool_contradicts(evidence, finding)
        # Should not contradict
        assert result is False


class TestContradictsPattern:
    """Tests for _contradicts_pattern method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.python_config.mypy_configured.value = True
        context.python_config.mypy_strict.value = False
        context.python_config.uses_result_pattern.value = True
        context.shell_config.strict_mode_files = set()
        return context

    def test_contradicts_pattern_with_result_pattern(self, mock_context):
        """Test _contradicts_pattern with Result pattern."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=10,
            category="error_handling",
            severity="Low",
            confidence=50,
            description="Exception raised without handling",
            source_agent="test",
        )

        result = validation._contradicts_pattern(finding)
        # Should contradict because project uses Result pattern
        assert result is True

    def test_contradicts_pattern_no_contradiction(self, mock_context):
        """Test _contradicts_pattern returns False when no contradiction."""
        validation = ValidationPass(mock_context, ValidationMode.FAST)

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Code style issue",
            source_agent="test",
        )

        result = validation._contradicts_pattern(finding)
        # Should not contradict
        assert result is False


class TestValidateFinding:
    """Tests for validate_finding method with evidence."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.python_config.mypy_configured.value = True
        context.python_config.mypy_strict.value = False
        context.python_config.uses_result_pattern.value = True
        context.shell_config.strict_mode_files = set()
        return context

    @patch.object(ValidationPass, "_get_evidence")
    def test_validate_finding_with_confirmation(self, mock_get_evidence, mock_context):
        """Test validate_finding adds CONFIRMED evidence ref."""
        mock_get_evidence.return_value = [
            Evidence(
                source="ruff",
                file="src/auth.py",
                line=10,
                message="unused import os",
                severity="warning",
                code="F401",
            )
        ]

        validation = ValidationPass(mock_context, ValidationMode.FAST)

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="unused import os",
            source_agent="test",
            evidence_refs=frozenset(),
        )

        validated = validation.validate_finding(finding)

        # Should have CONFIRMED evidence ref
        assert any(ref.startswith("CONFIRMED:") for ref in validated.evidence_refs)

    @patch.object(ValidationPass, "_get_evidence")
    def test_validate_finding_with_contradiction(self, mock_get_evidence, mock_context):
        """Test validate_finding sets confidence to 0 on contradiction."""
        mock_get_evidence.return_value = []

        validation = ValidationPass(mock_context, ValidationMode.FAST)

        finding = Finding(
            id="test-1",
            file="src/internal.py",
            line=10,
            category="type_annotation",
            severity="Low",
            confidence=50,
            description="Missing _type annotation for _internal function",
            source_agent="test",
            evidence_refs=frozenset(),
        )

        validated = validation.validate_finding(finding)

        # Should have confidence reduced to 0 due to contradiction
        assert validated.confidence == 0
        assert any(ref.startswith("CONTRADICTS:") for ref in validated.evidence_refs)

    @patch.object(ValidationPass, "_get_evidence")
    def test_validate_finding_with_pattern_contradiction(
        self, mock_get_evidence, mock_context
    ):
        """Test validate_finding reduces confidence on pattern contradiction."""
        mock_get_evidence.return_value = []

        validation = ValidationPass(mock_context, ValidationMode.FAST)

        finding = Finding(
            id="test-1",
            file="src/auth.py",
            line=10,
            category="error_handling",
            severity="Low",
            confidence=80,
            description="Exception raised without proper handling",
            source_agent="test",
            evidence_refs=frozenset(),
        )

        validated = validation.validate_finding(finding)

        # Should have confidence reduced due to Result pattern contradiction
        assert validated.confidence < 80
        assert any(ref.startswith("CONTRADICTS:") for ref in validated.evidence_refs)


class TestGetValidationSummary:
    """Tests for get_validation_summary method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.python_config.mypy_configured.value = True
        context.python_config.mypy_strict.value = False
        context.python_config.uses_result_pattern.value = True
        context.shell_config.strict_mode_files = set()
        return context

    @patch.object(ValidationPass, "_get_evidence")
    def test_get_validation_summary_confirmed(self, mock_get_evidence, mock_context):
        """Test get_validation_summary with confirmed findings."""
        mock_get_evidence.return_value = [
            Evidence(
                source="ruff",
                file="src/auth.py",
                line=10,
                message="unused import",
                severity="warning",
                code="F401",
            )
        ]

        validation = ValidationPass(mock_context, ValidationMode.FAST)

        findings = [
            Finding(
                id="test-1",
                file="src/auth.py",
                line=10,
                category="style",
                severity="Low",
                confidence=50,
                description="unused import",
                source_agent="test",
                evidence_refs=frozenset(),
            )
        ]

        summary = validation.get_validation_summary(findings)

        assert summary["total_findings"] == 1
        assert summary["confirmed_by_tools"] == 1
        assert summary["contradicted_by_tools"] == 0

    @patch.object(ValidationPass, "_get_evidence")
    def test_get_validation_summary_contrdicted(self, mock_get_evidence, mock_context):
        """Test get_validation_summary with contradicted findings."""
        mock_get_evidence.return_value = []

        validation = ValidationPass(mock_context, ValidationMode.FAST)

        findings = [
            Finding(
                id="test-1",
                file="src/internal.py",
                line=10,
                category="type_annotation",
                severity="Low",
                confidence=50,
                description="Missing _type annotation",
                source_agent="test",
                evidence_refs=frozenset(),
            )
        ]

        summary = validation.get_validation_summary(findings)

        assert summary["total_findings"] == 1
        assert summary["confirmed_by_tools"] == 0
        assert summary["contradicted_by_tools"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
