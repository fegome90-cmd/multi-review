#!/usr/bin/env python3
"""
XML finding parser for multi-review.

This module provides XML parsing for structured finding output.
Using XML tags makes parsing robust and eliminates regex fragility.

Dependencies:
    - Python 3.10+ stdlib only (xml.etree.ElementTree)
"""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import FrozenSet, List, Optional

# Add scripts to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from finding_filter import Finding

logger = logging.getLogger(__name__)


# =============================================================================
# XML SCHEMA
# =============================================================================

"""
Expected XML schema for findings:

<finding id="1" confidence="75" severity="Important">
  <file>src/auth.py</file>
  <line>45</line>
  <category>security</category>
  <description>SQL injection risk</description>
  <evidence>
    <ref tool="code-review">User input directly in query</ref>
  </evidence>
  <suggested_fix>Use parameterized queries</suggested_fix>
</finding>

Multiple findings can be wrapped in <findings>...</findings> or appear as siblings.
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _extract_xml_blocks(text: str) -> List[str]:
    """Extract XML finding blocks from mixed text.

    Handles cases where XML is embedded in markdown or other text.

    Args:
        text: Raw text that may contain XML blocks.

    Returns:
        List of XML string blocks (including <finding> tags).
    """
    blocks = []

    # Pattern for individual <finding>...</finding> blocks
    finding_pattern = re.compile(
        r'<finding[^>]*>.*?</finding>',
        re.DOTALL | re.IGNORECASE
    )

    for match in finding_pattern.finditer(text):
        blocks.append(match.group(0))

    return blocks


def _get_text(element: Optional[ET.Element], tag: str, default: str = "") -> str:
    """Get text content from a child element.

    Args:
        element: Parent XML element.
        tag: Tag name to find.
        default: Default value if not found.

    Returns:
        Text content or default.
    """
    if element is None:
        return default

    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()

    return default


def _parse_confidence(value: Optional[str]) -> int:
    """Parse confidence from attribute or text.

    Args:
        value: Confidence value as string.

    Returns:
        Integer confidence 0-100.
    """
    if value is None:
        return 50  # Default medium

    try:
        conf = int(value)
        return max(0, min(100, conf))
    except (ValueError, TypeError):
        # Try word-based confidence
        word_map = {
            'certain': 100,
            'high': 75,
            'medium': 50,
            'low': 25,
            'none': 0,
        }
        for word, score in word_map.items():
            if word in value.lower():
                return score

    return 50  # Default


def _parse_severity(value: Optional[str]) -> str:
    """Normalize severity from attribute or text.

    Args:
        value: Severity value as string.

    Returns:
        Normalized severity: Critical, Important, or Low.
    """
    if value is None:
        return "Low"

    severity_map = {
        'critical': 'Critical',
        'important': 'Important',
        'high': 'Important',
        'medium': 'Important',
        'low': 'Low',
        'suggestion': 'Low',
        'info': 'Low',
    }

    return severity_map.get(value.lower(), 'Low')


def _parse_evidence_refs(element: Optional[ET.Element]) -> FrozenSet[str]:
    """Parse evidence references from <evidence> element.

    Args:
        element: Parent XML element.

    Returns:
        FrozenSet of evidence reference strings.
    """
    refs = set()

    if element is None:
        return frozenset()

    evidence_elem = element.find('evidence')
    if evidence_elem is not None:
        for ref in evidence_elem.findall('ref'):
            if ref.text:
                # Include tool attribute if present
                tool = ref.get('tool', '')
                if tool:
                    refs.add(f"{tool}: {ref.text.strip()}")
                else:
                    refs.add(ref.text.strip())

    return frozenset(refs)


# =============================================================================
# MAIN PARSING FUNCTIONS
# =============================================================================

def _parse_single_finding(xml_str: str, agent_name: str, finding_num: int) -> Optional[Finding]:
    """Parse a single <finding> XML block into a Finding object.

    Args:
        xml_str: XML string for a single finding.
        agent_name: Name of the agent that produced this output.
        finding_num: Finding number for ID generation.

    Returns:
        Finding object, or None if parsing fails.
    """
    try:
        root = ET.fromstring(xml_str)

        # Get attributes
        finding_id = root.get('id', str(finding_num))
        confidence = _parse_confidence(root.get('confidence'))
        severity = _parse_severity(root.get('severity'))

        # Get child elements
        file_path = _get_text(root, 'file', 'unknown')
        line_str = _get_text(root, 'line', '0')
        category = _get_text(root, 'category', 'general')
        description = _get_text(root, 'description', '')
        suggested_fix = _get_text(root, 'suggested_fix') or None

        # Parse line number
        try:
            line = int(line_str)
        except ValueError:
            line = 0

        # Parse evidence refs
        evidence_refs = _parse_evidence_refs(root)

        # Add agent to evidence refs if not present
        if agent_name not in evidence_refs and agent_name != 'unknown':
            evidence_refs = evidence_refs | {agent_name}

        return Finding(
            id=f"{agent_name}-{finding_id}",
            file=file_path,
            line=line,
            category=category,
            severity=severity,
            confidence=confidence,
            description=description,
            suggested_fix=suggested_fix,
            evidence_refs=evidence_refs,
            source_agent=agent_name,
        )

    except ET.ParseError as e:
        logger.warning(f"Failed to parse XML finding: {e}")
        return None
    except ValueError as e:
        logger.warning(f"Invalid finding data in XML: {e}")
        return None


def parse_xml_findings(text: str, agent_name: str) -> List[Finding]:
    """Parse XML findings from text output.

    This function extracts <finding> XML blocks from text and parses them.
    It handles both pure XML output and XML embedded in markdown.

    Args:
        text: Raw output text that may contain XML findings.
        agent_name: Name of the agent that produced this output.

    Returns:
        List of Finding objects extracted from XML blocks.
    """
    findings = []

    # Extract XML blocks from text
    xml_blocks = _extract_xml_blocks(text)

    if not xml_blocks:
        return []

    logger.debug(f"Found {len(xml_blocks)} XML finding blocks")

    for i, xml_str in enumerate(xml_blocks, start=1):
        finding = _parse_single_finding(xml_str, agent_name, i)
        if finding is not None:
            findings.append(finding)

    logger.info(f"Parsed {len(findings)} findings from XML for {agent_name}")
    return findings


def has_xml_findings(text: str) -> bool:
    """Check if text contains XML finding blocks.

    Args:
        text: Text to check.

    Returns:
        True if XML findings are present.
    """
    return bool(_extract_xml_blocks(text))


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    # Test the parser with sample XML
    sample_xml = """
    Some text before.

    <finding id="1" confidence="75" severity="Important">
      <file>src/auth.py</file>
      <line>45</line>
      <category>security</category>
      <description>SQL injection risk in user input</description>
      <evidence>
        <ref tool="code-review">User input directly in query</ref>
      </evidence>
      <suggested_fix>Use parameterized queries</suggested_fix>
    </finding>

    <finding id="2" confidence="50" severity="Low">
      <file>src/utils.py</file>
      <line>12</line>
      <category>style</category>
      <description>Missing docstring</description>
    </finding>

    Some text after.
    """

    findings = parse_xml_findings(sample_xml, "test-agent")

    print(f"Parsed {len(findings)} findings:")
    for f in findings:
        print(f"  - [{f.id}] {f.severity} ({f.confidence}%): {f.description}")
        print(f"    File: {f.file}:{f.line}")
        print(f"    Category: {f.category}")
        if f.suggested_fix:
            print(f"    Fix: {f.suggested_fix}")
