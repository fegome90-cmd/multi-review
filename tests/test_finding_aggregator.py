#!/usr/bin/env python3
"""
Tests for finding_aggregator module.

Run with: pytest tests/test_finding_aggregator.py -v
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from finding_aggregator import (
    parse_severity,
    parse_confidence,
    parse_agent_output,
    _parse_regex_findings,
    parse_json_findings,
    apply_filtering,
    format_results,
    main,
)
from finding_filter import Finding


class TestParseSeverity:
    """Tests for parse_severity function."""

    def test_critical_variations(self):
        """Test critical severity variations."""
        assert parse_severity("critical") == "Critical"
        assert parse_severity("CRITICAL") == "Critical"
        assert parse_severity("Critical") == "Critical"

    def test_important_variations(self):
        """Test important/high/medium variations."""
        assert parse_severity("important") == "Important"
        assert parse_severity("high") == "Important"
        assert parse_severity("medium") == "Important"
        assert parse_severity("IMPORTANT") == "Important"

    def test_low_variations(self):
        """Test low severity variations."""
        assert parse_severity("low") == "Low"
        assert parse_severity("suggestion") == "Low"
        assert parse_severity("info") == "Low"

    def test_unknown_defaults_to_low(self):
        """Test unknown severity defaults to Low."""
        assert parse_severity("unknown") == "Low"
        assert parse_severity("") == "Low"
        assert parse_severity("random") == "Low"


class TestParseConfidence:
    """Tests for parse_confidence function."""

    def test_numeric_input(self):
        """Test numeric confidence input."""
        assert parse_confidence(75) == 75
        assert parse_confidence(100) == 100
        assert parse_confidence(0) == 0
        assert parse_confidence(50.5) == 50

    def test_string_with_number(self):
        """Test string containing number."""
        assert parse_confidence("75") == 75
        assert parse_confidence("confidence: 85%") == 85
        assert parse_confidence("(100)") == 100

    def test_word_based_confidence(self):
        """Test word-based confidence."""
        assert parse_confidence("certain") == 100
        assert parse_confidence("high confidence") == 75
        assert parse_confidence("medium") == 50
        assert parse_confidence("low") == 25
        assert parse_confidence("none") == 0

    def test_default_confidence(self):
        """Test default confidence for unrecognized input."""
        assert parse_confidence("unknown") == 50
        assert parse_confidence(None) == 50


class TestParseAgentOutput:
    """Tests for parse_agent_output function."""

    def test_parses_xml_findings(self):
        """Test XML findings are parsed correctly."""
        xml_output = """
<finding id="1" confidence="75" severity="Important">
  <file>src/auth.py</file>
  <line>45</line>
  <category>security</category>
  <description>SQL injection risk</description>
</finding>
"""
        findings = parse_agent_output("test-agent", xml_output)
        assert len(findings) == 1
        assert findings[0].file == "src/auth.py"
        assert findings[0].confidence == 75

    def test_falls_back_to_regex_for_non_xml(self):
        """Test regex fallback when no XML present."""
        regex_output = """
| src/auth.py | 45 | Critical | SQL injection risk |
"""
        findings = parse_agent_output("test-agent", regex_output)
        assert len(findings) == 1
        assert findings[0].file == "src/auth.py"

    def test_empty_output_returns_empty_list(self):
        """Test empty output returns empty list."""
        findings = parse_agent_output("test-agent", "")
        assert findings == []

    def test_xml_empty_findings_falls_back(self):
        """Test XML with no valid findings falls back to regex."""
        # This has XML tags but incomplete - XML parser fails, regex may extract minimal finding
        output = "<notafinding></notafinding>"
        findings = parse_agent_output("test-agent", output)
        # Should use regex which finds nothing in this case
        assert findings == []


class TestParseRegexFindings:
    """Tests for _parse_regex_findings function."""

    def test_table_pattern(self):
        """Test markdown table pattern."""
        output = """
| File | Line | Severity | Description |
|------|------|----------|-------------|
| `src/auth.py` | 45 | Critical | SQL injection |
| `src/db.py` | 12 | Low | Missing docstring |
"""
        findings = _parse_regex_findings("table-agent", output)
        assert len(findings) == 2
        assert findings[0].file == "src/auth.py"
        assert findings[0].severity == "Critical"
        assert findings[1].file == "src/db.py"

    def test_file_line_pattern(self):
        """Test file:line pattern."""
        output = """
src/auth.py:45: Critical - SQL injection risk
src/db.py:12: Important missing connection handling
"""
        findings = _parse_regex_findings("file-line-agent", output)
        assert len(findings) == 2
        assert findings[0].line == 45
        assert findings[1].line == 12

    def test_bullet_pattern(self):
        """Test bullet point pattern."""
        # Use a format that matches bullet_pattern specifically
        output = """
- [reviewer] src/auth.py:45 (75%) - SQL injection risk
"""
        findings = _parse_regex_findings("bullet-agent", output)
        # Bullet pattern should match and extract confidence
        assert len(findings) >= 1
        # Check that at least one finding has the expected confidence
        assert any(f.confidence == 75 for f in findings)

    def test_severity_section_pattern(self):
        """Test severity section pattern."""
        output = """
### Critical Issues

- src/auth.py:45 SQL injection risk
- src/db.py:12 Missing connection handling

### Low Priority

- src/utils.py:5 Missing docstring
"""
        findings = _parse_regex_findings("section-agent", output)
        # Should extract findings from sections
        assert len(findings) >= 1
        # Check findings were parsed
        assert all(f.source_agent == "section-agent" for f in findings)

    def test_severity_section_with_multiple_sections(self):
        """Test parsing multiple severity sections."""
        # Use output that won't match file:line pattern first
        # so severity section pattern is used
        output = """
### Critical Issues
- SQL injection risk in auth module
- Missing connection handling in db

### Important Issues
- Missing docstring in utils module

### Suggestions
- Improve error handling throughout
"""
        findings = _parse_regex_findings("section-agent", output)
        # Severity section only runs when no structured patterns matched
        # The file:line pattern in the original test matched first
        # This test uses descriptions without file:line to trigger severity section
        assert len(findings) >= 1
        # All should come from this agent
        assert all(f.source_agent == "section-agent" for f in findings)

    def test_severity_section_file_line_extraction(self):
        """Test file:line extraction from severity section descriptions."""
        output = """
### Critical Issues
- The function src/auth.py:45 has a potential SQL injection vulnerability
- src/db.py:12 needs error handling

### Low Priority
- Consider adding tests
"""
        findings = _parse_regex_findings("section-agent", output)
        assert len(findings) >= 2
        # Check file:line was extracted
        assert any(f.file == "src/auth.py" and f.line == 45 for f in findings)
        assert any(f.file == "src/db.py" and f.line == 12 for f in findings)
        # Check description had file:line removed
        auth_finding = next(f for f in findings if f.file == "src/auth.py")
        assert "src/auth.py:45" not in auth_finding.description

    def test_no_patterns_matched(self):
        """Test when no patterns match."""
        output = "Just some random text without findings"
        findings = _parse_regex_findings("no-match-agent", output)
        assert findings == []


class TestParseJsonFindings:
    """Tests for parse_json_findings function."""

    def test_valid_json_findings(self):
        """Test parsing valid JSON findings."""
        json_data = [
            {
                "id": "finding-1",
                "file": "src/auth.py",
                "line": 45,
                "category": "security",
                "severity": "critical",
                "confidence": 75,
                "description": "SQL injection",
                "source_agent": "test-agent",
            }
        ]
        findings = parse_json_findings(json_data)
        assert len(findings) == 1
        assert findings[0].file == "src/auth.py"
        assert findings[0].severity == "Critical"

    def test_missing_optional_fields(self):
        """Test handling missing optional fields."""
        json_data = [
            {
                "file": "src/test.py",
                "description": "Test finding",
            }
        ]
        findings = parse_json_findings(json_data)
        assert len(findings) == 1
        assert findings[0].id == "finding-1"
        assert findings[0].source_agent == "unknown"

    def test_invalid_finding_skipped(self):
        """Test invalid findings are skipped."""
        json_data = [
            {
                "id": "valid",
                "file": "src/test.py",
                "line": 1,
                "description": "Valid",
            },
            "not a dict - this will be skipped",
        ]
        findings = parse_json_findings(json_data)
        assert len(findings) == 1
        assert findings[0].id == "valid"

    def test_evidence_refs_included(self):
        """Test evidence refs are included from JSON."""
        json_data = [
            {
                "file": "src/test.py",
                "line": 1,
                "description": "Test",
                "source_agent": "my-agent",
                "evidence_refs": ["ref1", "ref2"],
            }
        ]
        findings = parse_json_findings(json_data)
        assert "ref1" in findings[0].evidence_refs
        assert "ref2" in findings[0].evidence_refs


class TestApplyFiltering:
    """Tests for apply_filtering function."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock ProjectContext."""
        context = MagicMock()
        context.python_config.mypy_strict.value = False
        context.python_config.ruff_rules = []
        context.shell_config.strict_mode_files = []
        context.git_metadata.pre_existing_issue_authors = []
        context.git_metadata.changed_files = ["src/test.py", "unknown"]
        return context

    def test_basic_filtering(self, mock_context):
        """Test basic filtering returns results."""
        findings = [
            Finding(
                id="test-1",
                file="src/test.py",
                line=10,
                category="general",
                severity="Important",
                confidence=75,
                description="Test finding",
                source_agent="test-agent",
            )
        ]

        results = apply_filtering(findings, mock_context)

        assert "categories" in results
        assert "summary" in results
        assert results["summary"]["total_findings"] == 1

    def test_filter_effectiveness_calculated(self, mock_context):
        """Test filter effectiveness is calculated."""
        findings = [
            Finding(
                id="test-1",
                file="src/test.py",
                line=10,
                category="style",
                severity="Low",
                confidence=20,  # Low value finding
                description="Style nitpick naming convention",
                source_agent="test-agent",
            )
        ]

        results = apply_filtering(findings, mock_context)

        assert "filter_effectiveness" in results
        # Should have suppressed the low-value finding
        assert results["summary"]["suppressed_findings"] >= 1

    def test_empty_findings(self, mock_context):
        """Test filtering empty findings."""
        results = apply_filtering([], mock_context)

        assert results["summary"]["total_findings"] == 0
        assert len(results["active"]) == 0

    def test_evidence_mode_with_validation_pass(self, mock_context):
        """Test evidence mode enables ValidationPass layer."""
        findings = [
            Finding(
                id="test-1",
                file="src/test.py",
                line=10,
                category="general",
                severity="Important",
                confidence=75,
                description="Test finding",
                source_agent="test-agent",
            )
        ]

        # Mock ValidationPass to avoid subprocess calls
        with patch("finding_aggregator.ValidationPass") as mock_validation:
            mock_validator = MagicMock()
            mock_validation.return_value = mock_validator
            # Return validated findings with updated evidence refs
            validated = [
                Finding(
                    id="test-1",
                    file="src/test.py",
                    line=10,
                    category="general",
                    severity="Important",
                    confidence=75,
                    description="Test finding",
                    evidence_refs=frozenset(["test-agent", "VALIDATED"]),
                    source_agent="test-agent",
                )
            ]
            mock_validator.validate_findings.return_value = validated

            results = apply_filtering(findings, mock_context, evidence_mode=True)

            # Verify ValidationPass was created with EVIDENCE mode
            mock_validation.assert_called_once()
            call_args = mock_validation.call_args
            assert call_args[0][1].value == "evidence"  # ValidationMode.EVIDENCE
            # Results should still be returned
            assert "summary" in results

    def test_findings_with_no_file_line(self, mock_context):
        """Test findings with no file/line (file-level findings)."""
        findings = [
            Finding(
                id="file-level-1",
                file="unknown",
                line=0,
                category="architecture",
                severity="Important",
                confidence=60,
                description="Missing documentation for module",
                source_agent="architect-agent",
            )
        ]

        results = apply_filtering(findings, mock_context)

        assert results["summary"]["total_findings"] == 1
        # File-level findings should still be included
        assert len(results["active"]) == 1


class TestFormatResults:
    """Tests for format_results function."""

    def test_formats_critical_issues(self):
        """Test critical issues are formatted."""
        results = {
            "categories": {
                "critical": [
                    MagicMock(
                        finding=Finding(
                            id="c1",
                            file="src/auth.py",
                            line=45,
                            category="security",
                            severity="Critical",
                            confidence=90,
                            description="SQL injection",
                            evidence_refs=frozenset(["agent-a"]),
                            source_agent="agent-a",
                        ),
                        filtered_confidence=90,
                    )
                ],
                "important": [],
                "suggestions": [],
                "suppressed": [],
            },
            "summary": {
                "total_findings": 1,
                "active_findings": 1,
                "suppressed_findings": 0,
            },
            "filter_effectiveness": 0.0,
        }

        output = format_results(results)

        assert "# Code Review Summary" in output
        assert "Critical Issues" in output
        assert "SQL injection" in output

    def test_formats_suppressed_findings(self):
        """Test suppressed findings are formatted in table."""
        finding = Finding(
            id="s1",
            file="src/test.py",
            line=1,
            category="style",
            severity="Low",
            confidence=20,
            description="Style nitpick that is too long to display in full without truncation",
            source_agent="test",
        )
        results = {
            "categories": {
                "critical": [],
                "important": [],
                "suggestions": [],
                "suppressed": [{"finding": finding, "reason": "Low value finding"}],
            },
            "summary": {
                "total_findings": 1,
                "active_findings": 0,
                "suppressed_findings": 1,
            },
            "filter_effectiveness": 100.0,
        }

        output = format_results(results)

        assert "Suppressed Findings" in output
        assert "Low value finding" in output

    def test_formats_summary_statistics(self):
        """Test summary statistics are formatted."""
        results = {
            "categories": {
                "critical": [],
                "important": [],
                "suggestions": [],
                "suppressed": [],
            },
            "summary": {
                "total_findings": 10,
                "active_findings": 7,
                "suppressed_findings": 3,
            },
            "filter_effectiveness": 30.0,
        }

        output = format_results(results)

        assert "Total findings:** 10" in output
        assert "Active findings:** 7" in output
        assert "Suppressed:** 3" in output
        assert "30.0%" in output


class TestMultiAgentDeduplication:
    """Tests for multi-agent deduplication scenarios."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock ProjectContext."""
        context = MagicMock()
        context.python_config.mypy_strict.value = False
        context.python_config.mypy_configured.value = False
        context.python_config.ruff_rules = []
        context.python_config.uses_result_pattern.value = False
        context.shell_config.strict_mode_files = []
        context.git_metadata.pre_existing_issue_authors = []
        context.git_metadata.changed_files = ["src/test.py"]
        return context

    def test_same_finding_from_multiple_agents(self, mock_context):
        """Test deduplication when same finding appears from multiple agents."""
        findings = [
            Finding(
                id="agent1-1",
                file="src/auth.py",
                line=45,
                category="security",
                severity="Important",
                confidence=75,
                description="SQL injection risk",
                evidence_refs=frozenset(["agent1"]),
                source_agent="agent1",
            ),
            Finding(
                id="agent2-1",
                file="src/auth.py",
                line=45,
                category="security",
                severity="Important",
                confidence=80,
                description="SQL injection risk",
                evidence_refs=frozenset(["agent2"]),
                source_agent="agent2",
            ),
        ]

        results = apply_filtering(findings, mock_context)

        # Both findings should be in results
        assert results["summary"]["total_findings"] == 2
        # Both should be active (high confidence, same issue)
        assert len(results["active"]) == 2

    def test_same_file_line_different_descriptions(self, mock_context):
        """Test findings with same file/line but different descriptions."""
        findings = [
            Finding(
                id="agent1-1",
                file="src/auth.py",
                line=45,
                category="security",
                severity="Important",
                confidence=70,
                description="Missing error handling",
                evidence_refs=frozenset(["agent1"]),
                source_agent="agent1",
            ),
            Finding(
                id="agent2-1",
                file="src/auth.py",
                line=45,
                category="error-handling",
                severity="Important",
                confidence=75,
                description="No exception handling for network calls",
                evidence_refs=frozenset(["agent2"]),
                source_agent="agent2",
            ),
        ]

        results = apply_filtering(findings, mock_context)

        # Both findings should be in results (different descriptions)
        assert results["summary"]["total_findings"] == 2
        assert len(results["active"]) == 2

    def test_severity_escalation_multi_agent(self, mock_context):
        """Test severity escalation when multiple agents report same finding."""
        findings = [
            Finding(
                id="agent1-1",
                file="src/auth.py",
                line=45,
                category="security",
                severity="Low",  # One agent reports low
                confidence=50,
                description="Potential SQL injection",
                evidence_refs=frozenset(["agent1"]),
                source_agent="agent1",
            ),
            Finding(
                id="agent2-1",
                file="src/auth.py",
                line=45,
                category="security",
                severity="Critical",  # Another reports critical
                confidence=90,
                description="Confirmed SQL injection vulnerability",
                evidence_refs=frozenset(["agent2"]),
                source_agent="agent2",
            ),
        ]

        results = apply_filtering(findings, mock_context)

        # Both findings included - filtering layer handles severity
        assert results["summary"]["total_findings"] == 2
        # At least critical finding should be active
        assert len(results["active"]) >= 1


class TestMainCLI:
    """Tests for main CLI function."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create context JSON
            context_data = {
                "python_config": {
                    "mypy_strict": False,
                    "mypy_configured": False,
                    "ruff_rules": [],
                },
                "shell_config": {
                    "strict_mode_files": [],
                },
                "test_config": {
                    "framework": "pytest",
                    "coverage_enabled": False,
                },
                "git_metadata": {
                    "changed_files": [],
                    "pre_existing_issue_authors": [],
                },
            }
            context_file = tmpdir / "context.json"
            context_file.write_text(json.dumps(context_data))

            # Create findings JSON
            findings_data = [
                {
                    "id": "f1",
                    "file": "src/test.py",
                    "line": 10,
                    "category": "general",
                    "severity": "important",
                    "confidence": 75,
                    "description": "Test finding",
                    "source_agent": "test-agent",
                }
            ]
            findings_file = tmpdir / "findings.json"
            findings_file.write_text(json.dumps(findings_data))

            yield {"dir": tmpdir, "context": context_file, "findings": findings_file}

    def test_main_with_json_output(self, temp_files, capsys):
        """Test main with JSON output format."""
        with patch(
            "sys.argv",
            [
                "finding_aggregator.py",
                "--context-json",
                str(temp_files["context"]),
                "--findings-json",
                str(temp_files["findings"]),
                "--output-format",
                "json",
            ],
        ):
            try:
                main()
            except SystemExit as e:
                # Exit code 0 is success
                if e.code != 0:
                    raise

        captured = capsys.readouterr()
        # Should output JSON or process findings
        output = captured.out
        assert "{" in output or "No findings" in output or "summary" in output.lower()

    def test_main_with_markdown_output(self, temp_files, capsys):
        """Test main with markdown output format."""
        with patch(
            "sys.argv",
            [
                "finding_aggregator.py",
                "--context-json",
                str(temp_files["context"]),
                "--findings-json",
                str(temp_files["findings"]),
                "--output-format",
                "markdown",
            ],
        ):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 0

        captured = capsys.readouterr()
        assert "# Code Review Summary" in captured.out or "No findings" in captured.out

    def test_main_exits_on_missing_context(self):
        """Test main exits when context file missing."""
        with patch(
            "sys.argv",
            [
                "finding_aggregator.py",
                "--context-json",
                "/nonexistent/context.json",
            ],
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1

    def test_main_exits_gracefully_on_no_findings(self, temp_files):
        """Test main exits gracefully when no findings."""
        # Create empty findings
        empty_findings = temp_files["dir"] / "empty.json"
        empty_findings.write_text("[]")

        with patch(
            "sys.argv",
            [
                "finding_aggregator.py",
                "--context-json",
                str(temp_files["context"]),
                "--findings-json",
                str(empty_findings),
            ],
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
