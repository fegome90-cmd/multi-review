#!/usr/bin/env python3
"""
Tests for xml_finding_parser module.

Run with: pytest tests/test_xml_finding_parser.py -v
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from xml_finding_parser import (
    parse_xml_findings,
    has_xml_findings,
    _extract_xml_blocks,
    _parse_confidence,
    _parse_severity,
)


class TestExtractXmlBlocks:
    """Tests for _extract_xml_blocks function."""

    def test_pure_xml(self):
        """Test extracting from pure XML."""
        text = """<finding id="1" confidence="75" severity="Important">
  <file>src/auth.py</file>
  <line>45</line>
  <category>security</category>
  <description>Test issue</description>
</finding>"""
        blocks = _extract_xml_blocks(text)
        assert len(blocks) == 1

    def test_xml_in_markdown(self):
        """Test extracting XML embedded in markdown."""
        text = """
# Code Review

Here are the findings:

<finding id="1" confidence="75" severity="Important">
  <file>src/auth.py</file>
  <line>45</line>
  <category>security</category>
  <description>SQL injection</description>
</finding>

That's all!
"""
        blocks = _extract_xml_blocks(text)
        assert len(blocks) == 1

    def test_multiple_findings(self):
        """Test extracting multiple findings."""
        text = """
<finding id="1" confidence="75" severity="Important">
  <file>src/a.py</file>
  <line>1</line>
  <category>security</category>
  <description>Issue 1</description>
</finding>

<finding id="2" confidence="50" severity="Low">
  <file>src/b.py</file>
  <line>2</line>
  <category>style</category>
  <description>Issue 2</description>
</finding>
"""
        blocks = _extract_xml_blocks(text)
        assert len(blocks) == 2

    def test_no_xml(self):
        """Test when no XML is present."""
        text = "Just regular text without any XML tags"
        blocks = _extract_xml_blocks(text)
        assert len(blocks) == 0

    def test_malformed_xml_ignored(self):
        """Test that malformed XML doesn't crash."""
        text = """<finding id="1" confidence="75">
  <file>src/auth.py</file>
  <line>45</line>
  <!-- Missing closing tag -->
"""
        # Should not crash, just not extract
        blocks = _extract_xml_blocks(text)
        # Malformed XML won't be extracted
        assert len(blocks) == 0


class TestParseConfidence:
    """Tests for _parse_confidence function."""

    def test_numeric_confidence(self):
        """Test numeric confidence values."""
        assert _parse_confidence("75") == 75
        assert _parse_confidence("0") == 0
        assert _parse_confidence("100") == 100

    def test_word_confidence(self):
        """Test word-based confidence values."""
        assert _parse_confidence("certain") == 100
        assert _parse_confidence("high") == 75
        assert _parse_confidence("medium") == 50
        assert _parse_confidence("low") == 25
        assert _parse_confidence("none") == 0

    def test_word_in_sentence(self):
        """Test word in sentence."""
        assert _parse_confidence("High confidence") == 75
        assert _parse_confidence("I'm certain") == 100

    def test_invalid_defaults_to_50(self):
        """Test invalid values default to 50."""
        assert _parse_confidence(None) == 50
        assert _parse_confidence("invalid") == 50
        assert _parse_confidence("") == 50

    def test_out_of_range_clamped(self):
        """Test values outside 0-100 are clamped."""
        assert _parse_confidence("150") == 100
        assert _parse_confidence("-50") == 0


class TestParseSeverity:
    """Tests for _parse_severity function."""

    def test_valid_severities(self):
        """Test valid severity values."""
        assert _parse_severity("Critical") == "Critical"
        assert _parse_severity("critical") == "Critical"
        assert _parse_severity("IMPORTANT") == "Important"
        assert _parse_severity("high") == "Important"
        assert _parse_severity("medium") == "Important"
        assert _parse_severity("low") == "Low"
        assert _parse_severity("suggestion") == "Low"

    def test_invalid_defaults_to_low(self):
        """Test invalid values default to Low."""
        assert _parse_severity(None) == "Low"
        assert _parse_severity("unknown") == "Low"


class TestParseXmlFindings:
    """Tests for parse_xml_findings function."""

    def test_basic_parsing(self):
        """Test basic XML finding parsing."""
        xml = """<finding id="1" confidence="75" severity="Important">
  <file>src/auth.py</file>
  <line>45</line>
  <category>security</category>
  <description>SQL injection risk</description>
  <suggested_fix>Use parameterized queries</suggested_fix>
</finding>"""
        findings = parse_xml_findings(xml, "test-agent")
        assert len(findings) == 1

        f = findings[0]
        assert f.file == "src/auth.py"
        assert f.line == 45
        assert f.category == "security"
        assert f.severity == "Important"
        assert f.confidence == 75
        assert f.description == "SQL injection risk"
        assert f.suggested_fix == "Use parameterized queries"
        assert f.source_agent == "test-agent"

    def test_multiple_findings(self):
        """Test parsing multiple findings."""
        xml = """
<finding id="1" confidence="75" severity="Important">
  <file>src/a.py</file>
  <line>1</line>
  <category>security</category>
  <description>Issue 1</description>
</finding>

<finding id="2" confidence="50" severity="Low">
  <file>src/b.py</file>
  <line>2</line>
  <category>style</category>
  <description>Issue 2</description>
</finding>
"""
        findings = parse_xml_findings(xml, "multi-agent")
        assert len(findings) == 2

        assert findings[0].file == "src/a.py"
        assert findings[0].severity == "Important"
        assert findings[1].file == "src/b.py"
        assert findings[1].severity == "Low"

    def test_evidence_refs(self):
        """Test parsing evidence references."""
        xml = """<finding id="1" confidence="75" severity="Important">
  <file>src/auth.py</file>
  <line>45</line>
  <category>security</category>
  <description>Test</description>
  <evidence>
    <ref tool="code-review">Direct user input</ref>
    <ref tool="scanner">Pattern match</ref>
  </evidence>
</finding>"""
        findings = parse_xml_findings(xml, "test-agent")
        assert len(findings) == 1

        refs = findings[0].evidence_refs
        assert "code-review: Direct user input" in refs
        assert "scanner: Pattern match" in refs
        assert "test-agent" in refs  # Agent name added

    def test_minimal_finding(self):
        """Test parsing with minimal required fields."""
        xml = """<finding>
  <file>src/file.py</file>
  <description>Some issue</description>
</finding>"""
        findings = parse_xml_findings(xml, "minimal-agent")
        assert len(findings) == 1

        f = findings[0]
        assert f.file == "src/file.py"
        assert f.line == 0  # Default
        assert f.category == "general"  # Default
        assert f.severity == "Low"  # Default
        assert f.confidence == 50  # Default

    def test_no_xml_returns_empty(self):
        """Test that non-XML text returns empty list."""
        text = "Just some regular text without XML"
        findings = parse_xml_findings(text, "no-xml-agent")
        assert findings == []

    def test_malformed_xml_skipped(self):
        """Test that malformed XML is skipped gracefully."""
        xml = """
<finding id="1" confidence="75">
  <file>src/auth.py</file>
  <line>45</line>
  <description>Valid finding</description>
</finding>

<finding id="2">
  <!-- Malformed - missing required fields -->
</finding>

<finding id="3" confidence="50">
  <file>src/other.py</file>
  <line>10</line>
  <description>Another valid finding</description>
</finding>
"""
        # Should not crash, valid findings should be parsed
        findings = parse_xml_findings(xml, "mixed-agent")
        # At least the valid ones should be parsed
        assert len(findings) >= 1


class TestHasXmlFindings:
    """Tests for has_xml_findings function."""

    def test_returns_true_with_xml(self):
        """Test returns True when XML present."""
        text = """<finding id="1"><description>Test</description></finding>"""
        assert has_xml_findings(text) is True

    def test_returns_false_without_xml(self):
        """Test returns False when no XML present."""
        text = "No XML here"
        assert has_xml_findings(text) is False

    def test_returns_true_in_markdown(self):
        """Test returns True when XML in markdown."""
        text = """
# Heading

<finding id="1">
  <description>Test</description>
</finding>

More text.
"""
        assert has_xml_findings(text) is True


class TestFindingObjectValidation:
    """Tests that parsed findings pass Finding validation."""

    def test_confidence_bounds_enforced(self):
        """Test that confidence is within valid bounds."""
        # XML with out-of-range confidence
        xml = """<finding id="1" confidence="150">
  <file>src/test.py</file>
  <line>1</line>
  <description>Test</description>
</finding>"""
        findings = parse_xml_findings(xml, "bounds-agent")
        assert len(findings) == 1
        assert 0 <= findings[0].confidence <= 100

    def test_line_number_non_negative(self):
        """Test that negative line numbers are rejected."""
        xml = """<finding id="1" confidence="50">
  <file>src/test.py</file>
  <line>-5</line>
  <description>Test</description>
</finding>"""
        findings = parse_xml_findings(xml, "line-agent")
        # Finding with negative line is rejected (validation fails)
        assert len(findings) == 0

    def test_line_number_zero_is_valid(self):
        """Test that zero line number is valid."""
        xml = """<finding id="1" confidence="50">
  <file>src/test.py</file>
  <line>0</line>
  <description>Test</description>
</finding>"""
        findings = parse_xml_findings(xml, "line-agent")
        assert len(findings) == 1
        assert findings[0].line == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
